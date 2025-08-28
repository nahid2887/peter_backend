    # Month lay calendar for any user
   
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserAvailabilityViewSet,
    TimeSlotAvailabilityViewSet,
    month_availability_view,
    quick_availability_update,
    user_availability_list,
    day_availability_view,
    month_time_slot_availability_view,
    day_time_slot_availability_view,
    user_day_availability_view,
    user_month_availability_view
)

# Create router for ViewSets
router = DefaultRouter()
router.register(r'availability', UserAvailabilityViewSet, basename='user-availability')
router.register(r'time-slots', TimeSlotAvailabilityViewSet, basename='time-slot-availability')

urlpatterns = [
    # Include router URLs
    path('', include(router.urls)),
    
    # Custom endpoints with URL parameters (Old UserAvailability endpoints)
    path('month/', month_availability_view, name='month-availability'),
    path('day/', day_availability_view, name='day-availability'),
    path('quick-update/', quick_availability_update, name='quick-availability-update'),
    path('my-availability/', user_availability_list, name='user-availability-list'),




    # Simple endpoint: view any user's calendar for a date
    path('user-day-availability/<int:user_id>/', user_day_availability_view, name='user_day_availability'),
    # Month lay calendar for any user
    path('user-month-availability/<int:user_id>/', user_month_availability_view, name='user_month_availability'),

    # New TimeSlotAvailability endpoints
    path('time-slots/month/', month_time_slot_availability_view, name='month-time-slot-availability'),
    path('time-slots/day/', day_time_slot_availability_view, name='day-time-slot-availability'),
]
