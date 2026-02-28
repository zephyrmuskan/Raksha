import time
import math
import random

from django.contrib.auth import authenticate
from django.utils import timezone
from datetime import timedelta

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.authtoken.models import Token

from safety_app.models import (
    TrustedContact, Profile, UserLocation,
    SOSLog, JourneyTracker, IncidentReport
)
from safety_app.views import haversine, _send_sos_alert
from .serializers import (
    RegisterSerializer, UserSerializer, ProfileSerializer,
    TrustedContactSerializer, SOSLogSerializer,
    JourneySerializer, IncidentReportSerializer, NearbyAlertSerializer
)


# ─── Auth ────────────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([AllowAny])
def api_register(request):
    serializer = RegisterSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response({'token': token.key, 'username': user.username}, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def api_login(request):
    username = request.data.get('username', '').strip()
    password = request.data.get('password', '')
    user = authenticate(username=username, password=password)
    if user:
        token, _ = Token.objects.get_or_create(user=user)
        return Response({'token': token.key, 'username': user.username})
    return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)


@api_view(['POST'])
def api_logout(request):
    request.user.auth_token.delete()
    return Response({'status': 'logged out'})


# ─── Profile & PINs ──────────────────────────────────────────────────────────

@api_view(['GET', 'PATCH'])
def api_profile(request):
    try:
        profile = request.user.profile
    except Profile.DoesNotExist:
        profile = Profile.objects.create(user=request.user)

    if request.method == 'GET':
        return Response(ProfileSerializer(profile).data)

    # PATCH — update PINs
    real_pin = request.data.get('real_pin', '').strip()
    duress_pin = request.data.get('duress_pin', '').strip()

    if not real_pin or not duress_pin:
        return Response({'error': 'Both PINs required'}, status=status.HTTP_400_BAD_REQUEST)
    if real_pin == duress_pin:
        return Response({'error': 'PINs must be different'}, status=status.HTTP_400_BAD_REQUEST)
    if not real_pin.isdigit() or not duress_pin.isdigit():
        return Response({'error': 'PINs must be numeric'}, status=status.HTTP_400_BAD_REQUEST)
    if len(real_pin) < 4 or len(duress_pin) < 4:
        return Response({'error': 'PINs must be at least 4 digits'}, status=status.HTTP_400_BAD_REQUEST)

    profile.real_pin = real_pin
    profile.duress_pin = duress_pin
    profile.save()
    return Response({'status': 'PINs updated'})


# ─── Trusted Contacts ────────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
def api_contacts(request):
    if request.method == 'GET':
        contacts = TrustedContact.objects.filter(user=request.user)
        return Response(TrustedContactSerializer(contacts, many=True).data)

    serializer = TrustedContactSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
def api_contact_delete(request, contact_id):
    try:
        contact = TrustedContact.objects.get(id=contact_id, user=request.user)
        contact.delete()
        return Response({'status': 'deleted'})
    except TrustedContact.DoesNotExist:
        return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)


# ─── SOS ─────────────────────────────────────────────────────────────────────

@api_view(['POST'])
def api_sos_trigger(request):
    user = request.user
    contacts = TrustedContact.objects.filter(user=user)
    trigger = request.data.get('trigger', 'triggered')
    lat = request.data.get('lat')
    lon = request.data.get('lon')

    try:
        profile = user.profile
        profile.is_sos_active = True
        profile.save()
    except Profile.DoesNotExist:
        Profile.objects.create(user=user, is_sos_active=True)

    _send_sos_alert(user, lat, lon, contacts, trigger_type=trigger)
    return Response({'status': 'sos_triggered'})


@api_view(['POST'])
def api_sos_deactivate(request):
    pin = request.data.get('pin', '')
    try:
        profile = request.user.profile
    except Profile.DoesNotExist:
        return Response({'error': 'Profile not found'}, status=status.HTTP_404_NOT_FOUND)

    if pin == profile.real_pin:
        profile.is_sos_active = False
        profile.save()
        SOSLog.objects.create(user=request.user, action='deactivated')
        return Response({'status': 'deactivated', 'duress': False})

    elif pin == profile.duress_pin:
        # Don't actually deactivate — covert alert
        SOSLog.objects.create(user=request.user, action='duress', notes='Duress PIN entered on mobile')
        from django.core.mail import send_mail
        from django.conf import settings as django_settings
        contacts = TrustedContact.objects.filter(user=request.user)
        if contacts:
            send_mail(
                'HIGH PRIORITY SILENT ALERT - DURESS PIN ENTERED',
                f'URGENT: {request.user.username} entered Duress PIN on mobile. Send immediate help!',
                django_settings.DEFAULT_FROM_EMAIL,
                [c.email for c in contacts]
            )
        return Response({'status': 'deactivated', 'duress': True})

    return Response({'error': 'Invalid PIN'}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def api_sos_status(request):
    try:
        profile = request.user.profile
        return Response({'is_sos_active': profile.is_sos_active})
    except Profile.DoesNotExist:
        return Response({'is_sos_active': False})


@api_view(['GET'])
def api_sos_history(request):
    logs = SOSLog.objects.filter(user=request.user)
    return Response(SOSLogSerializer(logs, many=True).data)


# ─── Location ────────────────────────────────────────────────────────────────

@api_view(['POST'])
def api_update_location(request):
    lat = request.data.get('lat')
    lon = request.data.get('lon')
    if lat and lon:
        loc, _ = UserLocation.objects.get_or_create(user=request.user)
        loc.latitude = float(lat)
        loc.longitude = float(lon)
        loc.save()
        return Response({'status': 'updated'})
    return Response({'error': 'lat/lon required'}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def api_check_alerts(request):
    try:
        my_loc = request.user.userlocation
        if not my_loc.latitude:
            return Response({'alerts': []})
    except UserLocation.DoesNotExist:
        return Response({'alerts': []})

    time_threshold = timezone.now() - timedelta(minutes=10)
    nearby_alerts = []
    active_users = UserLocation.objects.filter(
        last_updated__gte=time_threshold,
        user__profile__is_sos_active=True
    ).exclude(user=request.user)

    for au in active_users:
        if au.latitude is None or au.longitude is None:
            continue
        distance = haversine(my_loc.latitude, my_loc.longitude, au.latitude, au.longitude)
        if distance <= 5.0:
            nearby_alerts.append({
                'username': au.user.username,
                'distance': round(distance, 2),
                'lat': au.latitude,
                'lon': au.longitude,
            })

    return Response({'alerts': nearby_alerts})


# ─── Voice Analysis (Mock) ───────────────────────────────────────────────────

@api_view(['POST'])
def api_analyze_voice(request):
    time.sleep(0.3)
    danger_detected = random.random() > 0.90
    return Response({
        'danger_detected': danger_detected,
        'confidence': round(random.uniform(0.7, 0.99), 2) if danger_detected else 0.0
    })


# ─── Safe Walk / Journey ─────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
def api_journey(request):
    if request.method == 'GET':
        journey = JourneyTracker.objects.filter(user=request.user, status='active').first()
        if not journey:
            return Response({'active': False})
        serializer = JourneySerializer(journey)
        return Response({'active': True, **serializer.data})

    # POST — start new journey
    destination = request.data.get('destination', '').strip()
    eta = request.data.get('eta_minutes')

    if not destination or not eta:
        return Response({'error': 'destination and eta_minutes required'}, status=status.HTTP_400_BAD_REQUEST)

    JourneyTracker.objects.filter(user=request.user, status='active').update(status='cancelled')
    journey = JourneyTracker.objects.create(
        user=request.user,
        destination=destination,
        eta_minutes=int(eta),
    )
    return Response(JourneySerializer(journey).data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
def api_journey_arrive(request):
    journey = JourneyTracker.objects.filter(user=request.user, status='active').first()
    if journey:
        journey.status = 'arrived'
        journey.save()
        return Response({'status': 'arrived'})
    return Response({'error': 'No active journey'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
def api_journey_cancel(request):
    JourneyTracker.objects.filter(user=request.user, status='active').update(status='cancelled')
    return Response({'status': 'cancelled'})


# ─── Incidents ───────────────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
def api_incidents(request):
    if request.method == 'GET':
        cutoff = timezone.now() - timedelta(days=30)
        incidents = IncidentReport.objects.filter(reported_at__gte=cutoff)
        return Response(IncidentReportSerializer(incidents, many=True).data)

    serializer = IncidentReportSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
