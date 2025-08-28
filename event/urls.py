from django.urls import path
from . import views

app_name = 'event'

urlpatterns = [
    # Event endpoints
    path('events/', views.event_list, name='event_list'),
    path('events/create/', views.event_create, name='event_create'),
    path('events/<uuid:event_id>/', views.event_detail, name='event_detail'),
    path('events/<uuid:event_id>/update/', views.event_update, name='event_update'),
    path('events/<uuid:event_id>/delete/', views.event_delete, name='event_delete'),
    path('events/<uuid:event_id>/respond/', views.event_respond, name='event_respond'),
    path('events/<uuid:event_id>/responses/', views.event_responses, name='event_responses'),
    path('events/my_events/', views.my_events, name='my_events'),
    path('events/upcoming_events/', views.upcoming_events, name='upcoming_events'),
    
    # Ride request endpoints
    path('events/<uuid:event_id>/request_ride/', views.ride_request_create, name='ride_request_create'),
    path('events/<uuid:event_id>/ride-requests/', views.event_ride_requests, name='event_ride_requests'),
    path('ride-requests/<uuid:request_id>/', views.ride_request_detail, name='ride_request_detail'),
    path('ride-requests/<uuid:request_id>/cancel/', views.ride_request_cancel, name='ride_request_cancel'),
    
    # Accept ride request endpoint (simplified)
    path('ride-requests/<uuid:request_id>/accept/', views.accept_ride_request, name='accept_ride_request'),
]
