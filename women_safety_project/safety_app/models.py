from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class TrustedContact(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trusted_contacts')
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone_number = models.CharField(max_length=20)

    def __str__(self):
        return self.name

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    real_pin = models.CharField(max_length=10, default='1234')
    duress_pin = models.CharField(max_length=10, default='9999')
    is_sos_active = models.BooleanField(default=False)
    phone = models.CharField(max_length=15, blank=True, null=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"

class UserLocation(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s Location"


class SOSLog(models.Model):
    ACTION_CHOICES = [
        ('triggered', 'SOS Triggered'),
        ('deactivated', 'Deactivated (Real PIN)'),
        ('duress', 'Duress PIN Entered'),
        ('auto_panic', 'Auto (Panic Timer)'),
        ('auto_battery', 'Auto (Battery Critical)'),
        ('auto_shake', 'Auto (Shake Detected)'),
        ('auto_journey', 'Auto (Safe Walk Expired)'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sos_logs')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    notes = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user.username} — {self.action} @ {self.timestamp:%Y-%m-%d %H:%M}"


class JourneyTracker(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('arrived', 'Arrived Safe'),
        ('expired', 'Expired (SOS Fired)'),
        ('cancelled', 'Cancelled'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='journeys')
    destination = models.CharField(max_length=200)
    eta_minutes = models.PositiveIntegerField()
    started_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.user.username} → {self.destination} ({self.status})"


class IncidentReport(models.Model):
    SEVERITY_CHOICES = [
        ('low', 'Low — Suspicious activity'),
        ('medium', 'Medium — Harassment / Threat'),
        ('high', 'High — Physical danger'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='incident_reports')
    latitude = models.FloatField()
    longitude = models.FloatField()
    description = models.TextField(max_length=500)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES)
    reported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-reported_at']

    def __str__(self):
        return f"{self.severity.upper()} incident by {self.user.username} @ {self.reported_at:%Y-%m-%d %H:%M}"
