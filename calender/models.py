from django.db import models
from django.utils import timezone
from account.models import User
from datetime import datetime, timedelta, date


def get_today():
    """Helper function to get today's date for DateField default"""
    return timezone.now().date()


class AvailabilityStatus(models.TextChoices):
    AVAILABLE = 'available', 'Available'
    BUSY = 'busy', 'Busy'
    MAYBE = 'maybe', 'Maybe'


class RepeatType(models.TextChoices):
    ONCE = 'once', 'Just this once'
    WEEKLY = 'weekly', 'Repeat weekly'
    MONTHLY = 'monthly', 'Repeat monthly'


class TimeSlotType(models.TextChoices):
    MORNING = 'morning', 'Morning'
    AFTERNOON = 'afternoon', 'Afternoon'
    EVENING = 'evening', 'Evening'
    NIGHT = 'night', 'Night'


class TimeSlotAvailability(models.Model):
    """Individual time slot availability with its own repeat schedule"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='time_slot_availabilities')
    
    # Time slot type
    slot_type = models.CharField(
        max_length=20,
        choices=TimeSlotType.choices,
        help_text="Which time slot this availability applies to"
    )
    
    # Availability status for this specific slot
    status = models.CharField(
        max_length=20,
        choices=AvailabilityStatus.choices,
        default=AvailabilityStatus.AVAILABLE,
        help_text="Availability status for this time slot"
    )
    
    # Whether this slot is enabled/available
    is_available = models.BooleanField(default=True, help_text="Is this time slot available for playdates")
    
    # Individual repeat schedule for this time slot
    repeat_schedule = models.CharField(
        max_length=20,
        choices=RepeatType.choices,
        default=RepeatType.ONCE,
        help_text="How often this time slot availability repeats"
    )
    
    # Date range for this specific time slot
    start_date = models.DateField(default=get_today)
    end_date = models.DateField(null=True, blank=True)
    
    # Additional notes for this time slot
    notes = models.TextField(blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Time Slot Availability"
        verbose_name_plural = "Time Slot Availabilities"
        unique_together = ['user', 'slot_type', 'start_date']  # Prevent duplicate slots for same user/date
    
    def __str__(self):
        return f"{self.user.full_name} - {self.get_slot_type_display()} ({self.get_status_display()}) - {self.start_date}"
    
    def get_time_slot_info(self):
        """Return time slot information"""
        time_info = {
            'morning': {'name': 'Morning', 'time': '8:00-12:00'},
            'afternoon': {'name': 'Afternoon', 'time': '12:00-17:00'},
            'evening': {'name': 'Evening', 'time': '17:00-20:00'},
            'night': {'name': 'Night', 'time': '20:00-22:00'},
        }
        return time_info.get(self.slot_type, {'name': 'Unknown', 'time': '00:00-00:00'})
    
    @staticmethod
    def get_time_slot_info_static(slot_type):
        """Get the display information for a time slot type (static method)"""
        time_info = {
            'morning': {'name': 'Morning', 'time': '8:00-12:00'},
            'afternoon': {'name': 'Afternoon', 'time': '12:00-17:00'},
            'evening': {'name': 'Evening', 'time': '17:00-20:00'},
            'night': {'name': 'Night', 'time': '20:00-22:00'},
        }
        return time_info.get(slot_type, {'name': 'Unknown', 'time': '00:00-00:00'})
    
    def generate_end_date(self):
        """Auto-generate end date based on repeat schedule"""
        if self.repeat_schedule == RepeatType.ONCE:
            return self.start_date
        elif self.repeat_schedule == RepeatType.WEEKLY:
            return self.start_date + timedelta(days=7)
        elif self.repeat_schedule == RepeatType.MONTHLY:
            return self.start_date + timedelta(days=30)
        return self.start_date
    
    def is_active_on_date(self, date):
        """Check if this time slot availability is active on a specific date"""
        if date < self.start_date:
            return False
        if self.end_date and date > self.end_date:
            return False
        return True
    
    def save(self, *args, **kwargs):
        # Auto-generate end_date if not provided
        if not self.end_date:
            self.end_date = self.generate_end_date()
        super().save(*args, **kwargs)
    
    @classmethod
    def get_user_availability_for_date(cls, user, date):
        """Get all time slot availabilities for a user on a specific date"""
        availabilities = cls.objects.filter(
            user=user,
            start_date__lte=date,
            end_date__gte=date
        ).order_by('slot_type')
        
        return availabilities
    
    @classmethod
    def get_user_availability_for_month(cls, user, year, month):
        """Get user availability for a specific month"""
        from calendar import monthrange
        
        # Get first and last day of month
        first_day = datetime(year, month, 1).date()
        last_day = datetime(year, month, monthrange(year, month)[1]).date()
        
        # Get all time slot availabilities that might affect this month
        availabilities = cls.objects.filter(
            user=user,
            start_date__lte=last_day,
            end_date__gte=first_day
        ).order_by('-created_at')
        
        # Build month calendar data
        month_data = []
        for day in range(1, monthrange(year, month)[1] + 1):
            current_date = datetime(year, month, day).date()
            
            # Get all active time slots for this date
            day_slots = []
            for availability in availabilities:
                if availability.is_active_on_date(current_date):
                    slot_info = availability.get_time_slot_info()
                    day_slots.append({
                        'name': slot_info['name'],
                        'time': slot_info['time'],
                        'type': availability.slot_type,
                        'status': availability.status,
                        'status_display': availability.get_status_display(),
                        'repeat_schedule': availability.repeat_schedule,
                        'repeat_schedule_display': availability.get_repeat_schedule_display(),
                        'notes': availability.notes,
                        'availability_id': availability.id
                    })
            
            day_info = {
                'date': current_date,
                'day': day,
                'time_slots': day_slots,
                'total_available_slots': len([s for s in day_slots if s['status'] == 'available'])
            }
            month_data.append(day_info)
        
        return month_data


# Keep the old UserAvailability model for backward compatibility but mark it as deprecated
class UserAvailability(models.Model):
    """DEPRECATED: Use TimeSlotAvailability instead for individual slot control"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='availability_settings')
    
    # Individual Time Slot Availability with Status
    morning_status = models.CharField(
        max_length=20, 
        choices=AvailabilityStatus.choices, 
        default=AvailabilityStatus.AVAILABLE,
        help_text="Morning 8:00-12:00 availability status"
    )
    morning_available = models.BooleanField(default=False, help_text="Is morning slot enabled")
    
    afternoon_status = models.CharField(
        max_length=20, 
        choices=AvailabilityStatus.choices, 
        default=AvailabilityStatus.AVAILABLE,
        help_text="Afternoon 12:00-17:00 availability status"
    )
    afternoon_available = models.BooleanField(default=False, help_text="Is afternoon slot enabled")
    
    evening_status = models.CharField(
        max_length=20, 
        choices=AvailabilityStatus.choices, 
        default=AvailabilityStatus.AVAILABLE,
        help_text="Evening 17:00-20:00 availability status"
    )
    evening_available = models.BooleanField(default=False, help_text="Is evening slot enabled")
    
    night_status = models.CharField(
        max_length=20, 
        choices=AvailabilityStatus.choices, 
        default=AvailabilityStatus.AVAILABLE,
        help_text="Night 20:00-22:00 availability status"
    )
    night_available = models.BooleanField(default=False, help_text="Is night slot enabled")
    
    # Repeat Schedule
    repeat_schedule = models.CharField(
        max_length=20,
        choices=RepeatType.choices,
        default=RepeatType.ONCE
    )
    
    # Date range for the availability
    start_date = models.DateField(default=get_today)
    end_date = models.DateField(null=True, blank=True)
    
    # Additional notes
    notes = models.TextField(blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "User Availability"
        verbose_name_plural = "User Availabilities"
    
    def __str__(self):
        return f"{self.user.full_name} - {self.get_repeat_schedule_display()} ({self.start_date})"
    
    def get_available_time_slots(self):
        """Return list of available time slots with individual status"""
        slots = []
        if self.morning_available:
            slots.append({
                'name': 'Morning', 
                'time': '8:00-12:00', 
                'type': 'morning',
                'status': self.morning_status,
                'status_display': self.get_morning_status_display()
            })
        if self.afternoon_available:
            slots.append({
                'name': 'Afternoon', 
                'time': '12:00-17:00', 
                'type': 'afternoon',
                'status': self.afternoon_status,
                'status_display': self.get_afternoon_status_display()
            })
        if self.evening_available:
            slots.append({
                'name': 'Evening', 
                'time': '17:00-20:00', 
                'type': 'evening',
                'status': self.evening_status,
                'status_display': self.get_evening_status_display()
            })
        if self.night_available:
            slots.append({
                'name': 'Night', 
                'time': '20:00-22:00', 
                'type': 'night',
                'status': self.night_status,
                'status_display': self.get_night_status_display()
            })
        return slots
    
    def get_all_time_slots_with_status(self):
        """Return all time slots with their individual availability status"""
        return {
            'morning': {
                'name': 'Morning',
                'time': '8:00-12:00',
                'available': self.morning_available,
                'status': self.morning_status,
                'status_display': self.get_morning_status_display()
            },
            'afternoon': {
                'name': 'Afternoon', 
                'time': '12:00-17:00',
                'available': self.afternoon_available,
                'status': self.afternoon_status,
                'status_display': self.get_afternoon_status_display()
            },
            'evening': {
                'name': 'Evening',
                'time': '17:00-20:00', 
                'available': self.evening_available,
                'status': self.evening_status,
                'status_display': self.get_evening_status_display()
            },
            'night': {
                'name': 'Night',
                'time': '20:00-22:00',
                'available': self.night_available,
                'status': self.night_status,
                'status_display': self.get_night_status_display()
            }
        }
    
    def get_selected_day_names(self):
        """Return list of selected day names - removed since selected_days is not needed"""
        return []
    
    def is_available_on_date(self, date):
        """Check if user is available on a specific date"""
        # Check if date is within range
        if date < self.start_date:
            return False
        if self.end_date and date > self.end_date:
            return False
        
        # Since selected_days is removed, availability applies to all days in range
        return True
    
    def generate_end_date(self):
        """Auto-generate end date based on repeat schedule"""
        if self.repeat_schedule == RepeatType.ONCE:
            return self.start_date
        elif self.repeat_schedule == RepeatType.WEEKLY:
            return self.start_date + timedelta(days=7)
        elif self.repeat_schedule == RepeatType.MONTHLY:
            return self.start_date + timedelta(days=30)
        return self.start_date
    
    def save(self, *args, **kwargs):
        # Auto-generate end_date if not provided
        if not self.end_date:
            self.end_date = self.generate_end_date()
        super().save(*args, **kwargs)
    
    @classmethod
    def get_user_availability_for_month(cls, user, year, month):
        """Get user availability for a specific month"""
        from calendar import monthrange
        
        # Get first and last day of month
        first_day = datetime(year, month, 1).date()
        last_day = datetime(year, month, monthrange(year, month)[1]).date()
        
        # Get all availability records that might affect this month
        availabilities = cls.objects.filter(
            user=user,
            start_date__lte=last_day,
            end_date__gte=first_day
        ).order_by('-created_at')
        
        # Build month calendar data
        month_data = []
        for day in range(1, monthrange(year, month)[1] + 1):
            current_date = datetime(year, month, day).date()
            
            # Collect all time slots from all applicable availability records for this date
            all_time_slots = []
            notes_list = []
            
            for availability in availabilities:
                if availability.is_available_on_date(current_date):
                    # Get available time slots from this availability record
                    time_slots = availability.get_available_time_slots()
                    all_time_slots.extend(time_slots)
                    
                    # Collect notes (avoiding duplicates)
                    if availability.notes and availability.notes not in notes_list:
                        notes_list.append(availability.notes)
            
            # Remove duplicate time slots (in case multiple records have same slot)
            unique_slots = []
            seen_types = set()
            for slot in all_time_slots:
                if slot['type'] not in seen_types:
                    unique_slots.append(slot)
                    seen_types.add(slot['type'])
            
            day_info = {
                'date': current_date,
                'day': day,
                'time_slots': unique_slots,
                'notes': '; '.join(notes_list) if notes_list else None
            }
            month_data.append(day_info)
        
        return month_data



