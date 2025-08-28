from django.contrib import admin
from .models import UserAvailability, TimeSlotAvailability


@admin.register(UserAvailability)
class UserAvailabilityAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'start_date', 'end_date', 
        'repeat_schedule', 'get_time_slots_display', 'created_at'
    ]
    list_filter = ['repeat_schedule', 'start_date', 'created_at', 'morning_available', 'afternoon_available', 'evening_available', 'night_available']
    search_fields = ['user__full_name', 'user__email', 'notes']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'start_date'
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Schedule', {
            'fields': ('start_date', 'end_date', 'repeat_schedule')
        }),
        ('Morning Slot (8:00-12:00)', {
            'fields': ('morning_available', 'morning_status'),
            'classes': ('collapse',)
        }),
        ('Afternoon Slot (12:00-17:00)', {
            'fields': ('afternoon_available', 'afternoon_status'),
            'classes': ('collapse',)
        }),
        ('Evening Slot (17:00-20:00)', {
            'fields': ('evening_available', 'evening_status'),
            'classes': ('collapse',)
        }),
        ('Night Slot (20:00-22:00)', {
            'fields': ('night_available', 'night_status'),
            'classes': ('collapse',)
        }),
        ('Additional Info', {
            'fields': ('notes',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_time_slots_display(self, obj):
        slots = []
        if obj.morning_available:
            slots.append(f'Morning ({obj.get_morning_status_display()})')
        if obj.afternoon_available:
            slots.append(f'Afternoon ({obj.get_afternoon_status_display()})')
        if obj.evening_available:
            slots.append(f'Evening ({obj.get_evening_status_display()})')
        if obj.night_available:
            slots.append(f'Night ({obj.get_night_status_display()})')
        return ', '.join(slots) if slots else 'None'
    
    get_time_slots_display.short_description = 'Available Time Slots'


@admin.register(TimeSlotAvailability)
class TimeSlotAvailabilityAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'start_date', 'end_date', 'slot_type', 'status', 
        'repeat_schedule', 'is_available', 'created_at'
    ]
    list_filter = ['slot_type', 'status', 'repeat_schedule', 'is_available', 'start_date', 'created_at']
    search_fields = ['user__full_name', 'user__email', 'notes']
    readonly_fields = ['created_at', 'updated_at', 'get_time_slot_info_display']
    date_hierarchy = 'start_date'
    
    fieldsets = (
        ('User & Date Range', {
            'fields': ('user', 'start_date', 'end_date')
        }),
        ('Time Slot Configuration', {
            'fields': ('slot_type', 'status', 'is_available', 'repeat_schedule')
        }),
        ('Time Slot Info', {
            'fields': ('get_time_slot_info_display',),
            'classes': ('collapse',)
        }),
        ('Additional Info', {
            'fields': ('notes',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_time_slot_info_display(self, obj):
        info = obj.get_time_slot_info()
        return f"{info['name']}: {info['time']}"
    
    get_time_slot_info_display.short_description = 'Time Slot Details'
