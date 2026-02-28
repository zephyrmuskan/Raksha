from django.contrib import admin
from .models import TrustedContact, Profile, UserLocation, SOSLog, JourneyTracker, IncidentReport

admin.site.register(TrustedContact)
admin.site.register(Profile)
admin.site.register(UserLocation)
admin.site.register(SOSLog)
admin.site.register(JourneyTracker)
admin.site.register(IncidentReport)
