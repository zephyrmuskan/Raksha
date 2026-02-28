from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.decorators import login_required
from .models import TrustedContact, Profile, UserLocation, SOSLog, JourneyTracker, IncidentReport
from django.core.mail import send_mail
from django.http import JsonResponse
from django.utils import timezone
from django.conf import settings
import math, random, time
from datetime import timedelta


# ─── Auth Views ─────────────────────────────────────────────────────────────

def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            Profile.objects.create(user=user)
            UserLocation.objects.create(user=user)
            login(request, user)
            return redirect('home')
    else:
        form = UserCreationForm()
    return render(request, 'safety_app/register.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('home')
    else:
        form = AuthenticationForm()
    return render(request, 'safety_app/login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('login')


# ─── Core Pages ─────────────────────────────────────────────────────────────

@login_required
def home(request):
    is_sos_active = request.session.get('sos_active', False)
    # Get active journey if any
    active_journey = JourneyTracker.objects.filter(user=request.user, status='active').first()
    return render(request, 'safety_app/home.html', {
        'sos_active': is_sos_active,
        'active_journey': active_journey,
    })

@login_required
def profile_settings(request):
    try:
        profile = request.user.profile
    except Profile.DoesNotExist:
        profile = Profile.objects.create(user=request.user)

    success = False
    error = None

    if request.method == 'POST':
        real_pin = request.POST.get('real_pin', '').strip()
        duress_pin = request.POST.get('duress_pin', '').strip()

        if not real_pin or not duress_pin:
            error = 'Both PINs are required.'
        elif real_pin == duress_pin:
            error = 'Real PIN and Duress PIN must be different.'
        elif not real_pin.isdigit() or not duress_pin.isdigit():
            error = 'PINs must contain only numbers.'
        elif len(real_pin) < 4 or len(duress_pin) < 4:
            error = 'PINs must be at least 4 digits.'
        else:
            profile.real_pin = real_pin
            profile.duress_pin = duress_pin
            profile.save()
            success = True

    return render(request, 'safety_app/profile.html', {
        'profile': profile,
        'success': success,
        'error': error,
    })


# ─── Trusted Contacts ────────────────────────────────────────────────────────

@login_required
def trusted_contacts(request):
    contacts = TrustedContact.objects.filter(user=request.user)
    return render(request, 'safety_app/trusted_contacts.html', {'contacts': contacts})

@login_required
def add_trusted_contact(request):
    if request.method == 'POST':
        name = request.POST['name']
        email = request.POST['email']
        phone_number = request.POST['phone_number']
        TrustedContact.objects.create(user=request.user, name=name, email=email, phone_number=phone_number)
        return redirect('trusted_contacts')
    return render(request, 'safety_app/add_trusted_contact.html')

@login_required
def delete_trusted_contact(request, contact_id):
    contact = get_object_or_404(TrustedContact, id=contact_id)
    if contact.user == request.user:
        contact.delete()
    return redirect('trusted_contacts')


# ─── SOS ─────────────────────────────────────────────────────────────────────

def _send_sos_alert(user, lat, lon, contacts, trigger_type='triggered'):
    """Helper to send SOS alerts + mock SMS and create a log entry."""
    lat_val = lat or 'Unknown'
    lon_val = lon or 'Unknown'

    # Log to database
    SOSLog.objects.create(
        user=user,
        action=trigger_type,
        latitude=float(lat) if lat else None,
        longitude=float(lon) if lon else None,
    )

    if contacts:
        map_url = f'https://www.google.com/maps/search/?api=1&query={lat_val},{lon_val}'
        subject = 'SOS Alert'
        message = f'{user.username} is in an emergency. Location: {map_url}'
        recipient_list = [contact.email for contact in contacts]
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipient_list)

        # Mock SMS Gateway
        print("\n" + "!"*60)
        print("🚨 URGENT SOS ALERT INITIATED 🚨")
        print(f"Trigger: {trigger_type.upper()} | User: {user.username}")
        print(f"Location Map: {map_url}")
        print("-" * 60)
        for contact in contacts:
            print(f"📡 [SMS GATEWAY]: Sending to +{contact.phone_number} ({contact.name})...")
            time.sleep(0.3)
            print(f"✅  SMS DELIVERED to {contact.name}")
        print("!"*60 + "\n")


@login_required
def sos(request):
    if request.method == 'POST':
        user = request.user
        contacts = TrustedContact.objects.filter(user=user)
        request.session['sos_active'] = True
        trigger = request.POST.get('trigger', 'triggered')

        try:
            profile = user.profile
            profile.is_sos_active = True
            profile.save()
        except Profile.DoesNotExist:
            profile = Profile.objects.create(user=user, is_sos_active=True)

        lat = request.POST.get('lat')
        lon = request.POST.get('lon')
        _send_sos_alert(user, lat, lon, contacts, trigger_type=trigger)
        return redirect('home')
    return redirect('home')


@login_required
def deactivate_sos(request):
    if request.method == 'POST':
        pin = request.POST.get('pin')
        try:
            profile = request.user.profile
        except Profile.DoesNotExist:
            profile = Profile.objects.create(user=request.user)

        if pin == profile.real_pin:
            request.session['sos_active'] = False
            profile.is_sos_active = False
            profile.save()

            # Log deactivation
            SOSLog.objects.create(user=request.user, action='deactivated')

            user = request.user
            contacts = TrustedContact.objects.filter(user=user)
            if contacts:
                print("\n" + "="*60)
                print("🟢 SOS DEACTIVATED - USER IS SAFE 🟢")
                print("-" * 60)
                for contact in contacts:
                    print(f"📡 [SMS GATEWAY]: Sending 'Safe' update to +{contact.phone_number}...")
                    time.sleep(0.3)
                    print(f"✅  SMS DELIVERED: '{user.username} is now safe.'")
                print("="*60 + "\n")

            return redirect('home')

        elif pin == profile.duress_pin:
            request.session['sos_active'] = False
            # Do NOT set is_sos_active = False — keeps community alert live

            # Log duress event
            SOSLog.objects.create(user=request.user, action='duress', notes='Duress PIN entered; covert alert sent')

            user = request.user
            contacts = TrustedContact.objects.filter(user=user)
            if contacts:
                subject = 'HIGH PRIORITY SILENT ALERT - DURESS PIN ENTERED'
                message = f'URGENT: {user.username} entered their DURESS PIN. They may be forced to deactivate. Send immediate help!'
                recipient_list = [contact.email for contact in contacts]
                send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipient_list)

                print("\n" + "X"*60)
                print("☠️  DURESS PIN DETECTED - COVERT HIGH-PRIORITY DISPATCH ☠️")
                for contact in contacts:
                    print(f"📡 [SECURE SMS]: Sending covert alert to +{contact.phone_number}...")
                    time.sleep(0.3)
                    print(f"🚨  CRITICAL SMS DELIVERED to {contact.name}")
                print("X"*60 + "\n")

            return redirect('home')
        else:
            return render(request, 'safety_app/home.html', {
                'sos_active': True,
                'error': 'Invalid PIN'
            })
    return redirect('home')


# ─── SOS History ─────────────────────────────────────────────────────────────

@login_required
def sos_history(request):
    logs = SOSLog.objects.filter(user=request.user)
    return render(request, 'safety_app/sos_history.html', {'logs': logs})


# ─── Location & Community Alerts ─────────────────────────────────────────────

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = math.sin(dLat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dLon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

@login_required
def update_location(request):
    if request.method == 'POST':
        lat = request.POST.get('lat')
        lon = request.POST.get('lon')
        if lat and lon:
            loc, _ = UserLocation.objects.get_or_create(user=request.user)
            loc.latitude = float(lat)
            loc.longitude = float(lon)
            loc.save()
            return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=400)

@login_required
def check_alerts(request):
    try:
        my_loc = request.user.userlocation
        if not my_loc.latitude:
            return JsonResponse({'alerts': []})
    except UserLocation.DoesNotExist:
        return JsonResponse({'alerts': []})

    time_threshold = timezone.now() - timedelta(minutes=10)
    nearby_alerts = []

    active_users = UserLocation.objects.filter(
        last_updated__gte=time_threshold,
        user__profile__is_sos_active=True
    ).exclude(user=request.user)

    for active_user in active_users:
        if active_user.latitude is None or active_user.longitude is None:
            continue
        distance = haversine(my_loc.latitude, my_loc.longitude, active_user.latitude, active_user.longitude)
        if distance <= 5.0:
            nearby_alerts.append({
                'username': active_user.user.username,
                'distance': round(distance, 2),
                'lat': active_user.latitude,
                'lon': active_user.longitude,
            })

    return JsonResponse({'alerts': nearby_alerts})


# ─── Voice Analysis ───────────────────────────────────────────────────────────

@login_required
def analyze_voice(request):
    if request.method == 'POST':
        time.sleep(0.5)
        danger_detected = random.random() > 0.90
        return JsonResponse({
            'status': 'success',
            'danger_detected': danger_detected,
            'confidence': round(random.uniform(0.7, 0.99), 2) if danger_detected else 0.0
        })
    return JsonResponse({'status': 'error'}, status=400)


# ─── Safe Route ───────────────────────────────────────────────────────────────

@login_required
def safe_route(request):
    return render(request, 'safety_app/safe_route.html')


# ─── Safe Walk / Journey Tracker ─────────────────────────────────────────────

@login_required
def safe_walk(request):
    # Cancel any other active journeys first
    active_journeys = JourneyTracker.objects.filter(user=request.user, status='active')

    if request.method == 'POST':
        destination = request.POST.get('destination', '').strip()
        eta = request.POST.get('eta_minutes', '').strip()

        if destination and eta and eta.isdigit() and int(eta) > 0:
            active_journeys.update(status='cancelled')
            journey = JourneyTracker.objects.create(
                user=request.user,
                destination=destination,
                eta_minutes=int(eta),
            )
            return redirect('home')

    return render(request, 'safety_app/safe_walk.html', {
        'active_journey': active_journeys.first(),
    })

@login_required
def arrive_safe(request):
    if request.method == 'POST':
        journey = JourneyTracker.objects.filter(user=request.user, status='active').first()
        if journey:
            journey.status = 'arrived'
            journey.save()
            return JsonResponse({'status': 'arrived'})
    return JsonResponse({'status': 'error'}, status=400)

@login_required
def check_journey(request):
    """AJAX poll — returns remaining seconds for active journey, or -1 if none."""
    journey = JourneyTracker.objects.filter(user=request.user, status='active').first()
    if not journey:
        return JsonResponse({'active': False})

    elapsed = (timezone.now() - journey.started_at).total_seconds()
    total_seconds = journey.eta_minutes * 60
    remaining = total_seconds - elapsed

    if remaining <= 0:
        # Mark expired
        journey.status = 'expired'
        journey.save()
        return JsonResponse({'active': True, 'expired': True, 'destination': journey.destination})

    return JsonResponse({
        'active': True,
        'expired': False,
        'remaining_seconds': int(remaining),
        'destination': journey.destination,
    })


# ─── Incident Reports ────────────────────────────────────────────────────────

@login_required
def log_incident(request):
    if request.method == 'POST':
        lat = request.POST.get('latitude')
        lon = request.POST.get('longitude')
        description = request.POST.get('description', '').strip()
        severity = request.POST.get('severity', 'low')

        if lat and lon and description:
            IncidentReport.objects.create(
                user=request.user,
                latitude=float(lat),
                longitude=float(lon),
                description=description,
                severity=severity,
            )
            return redirect('incident_success')

    return render(request, 'safety_app/incident_report.html')

@login_required
def incident_success(request):
    return render(request, 'safety_app/incident_success.html')

@login_required
def get_incidents(request):
    """AJAX endpoint — returns recent incident reports as JSON for heatmap."""
    cutoff = timezone.now() - timedelta(days=30)
    incidents = IncidentReport.objects.filter(reported_at__gte=cutoff).values(
        'latitude', 'longitude', 'severity', 'description', 'reported_at'
    )
    data = []
    for inc in incidents:
        data.append({
            'lat': inc['latitude'],
            'lon': inc['longitude'],
            'severity': inc['severity'],
            'description': inc['description'],
        })
    return JsonResponse({'incidents': data})
