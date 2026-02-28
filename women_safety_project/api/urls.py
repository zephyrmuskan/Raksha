from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('auth/register/', views.api_register, name='api_register'),
    path('auth/login/', views.api_login, name='api_login'),
    path('auth/logout/', views.api_logout, name='api_logout'),

    # Profile
    path('profile/', views.api_profile, name='api_profile'),

    # Contacts
    path('contacts/', views.api_contacts, name='api_contacts'),
    path('contacts/<int:contact_id>/', views.api_contact_delete, name='api_contact_delete'),

    # SOS
    path('sos/trigger/', views.api_sos_trigger, name='api_sos_trigger'),
    path('sos/deactivate/', views.api_sos_deactivate, name='api_sos_deactivate'),
    path('sos/status/', views.api_sos_status, name='api_sos_status'),
    path('sos/history/', views.api_sos_history, name='api_sos_history'),

    # Location & Alerts
    path('location/update/', views.api_update_location, name='api_update_location'),
    path('location/alerts/', views.api_check_alerts, name='api_check_alerts'),

    # Voice
    path('voice/analyze/', views.api_analyze_voice, name='api_analyze_voice'),

    # Journey / Safe Walk
    path('journey/', views.api_journey, name='api_journey'),
    path('journey/arrive/', views.api_journey_arrive, name='api_journey_arrive'),
    path('journey/cancel/', views.api_journey_cancel, name='api_journey_cancel'),

    # Incidents
    path('incidents/', views.api_incidents, name='api_incidents'),
]
