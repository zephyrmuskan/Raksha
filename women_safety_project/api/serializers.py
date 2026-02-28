from rest_framework import serializers
from django.contrib.auth.models import User
from safety_app.models import TrustedContact, Profile, SOSLog, JourneyTracker, IncidentReport, UserLocation


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email']


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(min_length=8, write_only=True)
    password2 = serializers.CharField(write_only=True)

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("A user with that username already exists.")
        return value

    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError({"password": "Passwords do not match."})
        return data

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            password=validated_data['password'],
        )
        Profile.objects.create(user=user)
        UserLocation.objects.create(user=user)
        return user


class TrustedContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrustedContact
        fields = ['id', 'name', 'email', 'phone_number']
        read_only_fields = ['id']


class ProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Profile
        fields = ['username', 'real_pin', 'duress_pin', 'phone', 'is_sos_active']
        read_only_fields = ['is_sos_active']


class SOSLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = SOSLog
        fields = ['id', 'action', 'latitude', 'longitude', 'timestamp', 'notes']
        read_only_fields = ['id', 'timestamp']


class JourneySerializer(serializers.ModelSerializer):
    started_at = serializers.DateTimeField(read_only=True)
    remaining_seconds = serializers.SerializerMethodField()

    class Meta:
        model = JourneyTracker
        fields = ['id', 'destination', 'eta_minutes', 'started_at', 'status', 'remaining_seconds']
        read_only_fields = ['id', 'started_at', 'status']

    def get_remaining_seconds(self, obj):
        if obj.status != 'active':
            return 0
        from django.utils import timezone
        elapsed = (timezone.now() - obj.started_at).total_seconds()
        remaining = obj.eta_minutes * 60 - elapsed
        return max(0, int(remaining))


class IncidentReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = IncidentReport
        fields = ['id', 'latitude', 'longitude', 'description', 'severity', 'reported_at']
        read_only_fields = ['id', 'reported_at']


class NearbyAlertSerializer(serializers.Serializer):
    username = serializers.CharField()
    distance = serializers.FloatField()
    lat = serializers.FloatField()
    lon = serializers.FloatField()
