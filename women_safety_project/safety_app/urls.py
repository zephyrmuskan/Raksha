from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Core
    path('', views.home, name='home'),
    path('profile/', views.profile_settings, name='profile_settings'),

    # Trusted Contacts
    path('trusted_contacts/', views.trusted_contacts, name='trusted_contacts'),
    path('add_trusted_contact/', views.add_trusted_contact, name='add_trusted_contact'),
    path('delete_trusted_contact/<int:contact_id>/', views.delete_trusted_contact, name='delete_trusted_contact'),

    # SOS
    path('sos/', views.sos, name='sos'),
    path('deactivate_sos/', views.deactivate_sos, name='deactivate_sos'),
    path('sos_history/', views.sos_history, name='sos_history'),

    # Location & Alerts
    path('update_location/', views.update_location, name='update_location'),
    path('check_alerts/', views.check_alerts, name='check_alerts'),

    # Voice
    path('analyze_voice/', views.analyze_voice, name='analyze_voice'),

    # Safe Route
    path('safe_route/', views.safe_route, name='safe_route'),

    # Safe Walk / Journey Tracker
    path('safe_walk/', views.safe_walk, name='safe_walk'),
    path('arrive_safe/', views.arrive_safe, name='arrive_safe'),
    path('check_journey/', views.check_journey, name='check_journey'),

    # Incidents
    path('incident_report/', views.log_incident, name='incident_report'),
    path('incident_report/success/', views.incident_success, name='incident_success'),
    path('get_incidents/', views.get_incidents, name='get_incidents'),
]
