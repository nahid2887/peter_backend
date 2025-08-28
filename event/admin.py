from django.contrib import admin
from .models import Event, EventInvite, EventResponse, RideRequest, RideOffer, RideMatch


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['title', 'date', 'start_time', 'event_type', 'host', 'get_going_count', 'created_at']
    list_filter = ['event_type', 'date', 'add_to_google_calendar', 'ride_needed_for_event']
    search_fields = ['title', 'description', 'location', 'host__email', 'host__full_name']
    readonly_fields = ['id', 'created_at', 'updated_at', 'google_calendar_event_id']
    date_hierarchy = 'date'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'host')
        }),
        ('Date and Time', {
            'fields': ('date', 'start_time', 'end_time')
        }),
        ('Event Details', {
            'fields': ('location', 'event_type')
        }),
        ('Options', {
            'fields': ('add_to_google_calendar', 'ride_needed_for_event', 'google_calendar_event_id')
        }),
        ('System', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_going_count(self, obj):
        return obj.get_going_count()
    get_going_count.short_description = 'Going Count'


@admin.register(EventInvite)
class EventInviteAdmin(admin.ModelAdmin):
    list_display = ['event', 'invitee', 'invited_by', 'created_at']
    list_filter = ['created_at', 'event__event_type']
    search_fields = ['event__title', 'invitee__email', 'invitee__full_name']
    readonly_fields = ['id', 'created_at']


@admin.register(EventResponse)
class EventResponseAdmin(admin.ModelAdmin):
    list_display = ['event', 'user', 'response', 'updated_at']
    list_filter = ['response', 'updated_at', 'event__event_type']
    search_fields = ['event__title', 'user__email', 'user__full_name']
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(RideRequest)
class RideRequestAdmin(admin.ModelAdmin):
    list_display = ['event', 'requester', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['event__title', 'requester__email', 'requester__full_name']
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(RideOffer)
class RideOfferAdmin(admin.ModelAdmin):
    list_display = ['event', 'driver', 'available_seats', 'get_available_seats_count', 'is_available', 'created_at']
    list_filter = ['is_available', 'created_at']
    search_fields = ['event__title', 'driver__email', 'driver__full_name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    def get_available_seats_count(self, obj):
        return obj.get_available_seats_count()
    get_available_seats_count.short_description = 'Available Seats'


@admin.register(RideMatch)
class RideMatchAdmin(admin.ModelAdmin):
    list_display = ['ride_request', 'ride_offer', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['ride_request__requester__email', 'ride_offer__driver__email']
    readonly_fields = ['id', 'created_at', 'updated_at']
