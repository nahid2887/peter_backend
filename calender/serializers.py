from rest_framework import serializers
from .models import (
    UserAvailability,
    TimeSlotAvailability,
    AvailabilityStatus,
    RepeatType,
    TimeSlotType
)
from account.models import User
from datetime import datetime, timedelta


class TimeSlotAvailabilitySerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    repeat_schedule_display = serializers.CharField(source='get_repeat_schedule_display', read_only=True)
    slot_type_display = serializers.CharField(source='get_slot_type_display', read_only=True)
    time_slot_info = serializers.SerializerMethodField()
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    
    class Meta:
        model = TimeSlotAvailability
        fields = [
            'id', 'slot_type', 'slot_type_display', 'status', 'status_display',
            'is_available', 'repeat_schedule', 'repeat_schedule_display',
            'start_date', 'end_date', 'notes', 'time_slot_info',
            'user_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_time_slot_info(self, obj):
        return obj.get_time_slot_info()
    
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class MultipleTimeSlotSerializer(serializers.Serializer):
    """Serializer for setting multiple time slots with individual repeat schedules"""
    start_date = serializers.DateField()
    
    # Morning slot
    morning_available = serializers.BooleanField(default=False)
    morning_status = serializers.ChoiceField(choices=AvailabilityStatus.choices, default='available')
    morning_repeat = serializers.ChoiceField(choices=RepeatType.choices, default='once')
    morning_notes = serializers.CharField(required=False, allow_blank=True)
    
    # Afternoon slot  
    afternoon_available = serializers.BooleanField(default=False)
    afternoon_status = serializers.ChoiceField(choices=AvailabilityStatus.choices, default='available')
    afternoon_repeat = serializers.ChoiceField(choices=RepeatType.choices, default='once')
    afternoon_notes = serializers.CharField(required=False, allow_blank=True)
    
    # Evening slot
    evening_available = serializers.BooleanField(default=False)
    evening_status = serializers.ChoiceField(choices=AvailabilityStatus.choices, default='available')
    evening_repeat = serializers.ChoiceField(choices=RepeatType.choices, default='once')
    evening_notes = serializers.CharField(required=False, allow_blank=True)
    
    # Night slot
    night_available = serializers.BooleanField(default=False)
    night_status = serializers.ChoiceField(choices=AvailabilityStatus.choices, default='available')
    night_repeat = serializers.ChoiceField(choices=RepeatType.choices, default='once')
    night_notes = serializers.CharField(required=False, allow_blank=True)
    
    def save(self):
        user = self.context['request'].user
        start_date = self.validated_data['start_date']
        created_slots = []
        
        # Define slot configurations
        slots_config = [
            ('morning', 'morning_available', 'morning_status', 'morning_repeat', 'morning_notes'),
            ('afternoon', 'afternoon_available', 'afternoon_status', 'afternoon_repeat', 'afternoon_notes'),
            ('evening', 'evening_available', 'evening_status', 'evening_repeat', 'evening_notes'),
            ('night', 'night_available', 'night_status', 'night_repeat', 'night_notes'),
        ]
        
        for slot_type, available_key, status_key, repeat_key, notes_key in slots_config:
            if self.validated_data.get(available_key, False):
                # Create or update time slot availability
                slot_availability, created = TimeSlotAvailability.objects.get_or_create(
                    user=user,
                    slot_type=slot_type,
                    start_date=start_date,
                    defaults={
                        'status': self.validated_data.get(status_key, 'available'),
                        'is_available': True,
                        'repeat_schedule': self.validated_data.get(repeat_key, 'once'),
                        'notes': self.validated_data.get(notes_key, '')
                    }
                )
                
                if not created:
                    # Update existing
                    slot_availability.status = self.validated_data.get(status_key, 'available')
                    slot_availability.is_available = True
                    slot_availability.repeat_schedule = self.validated_data.get(repeat_key, 'once')
                    slot_availability.notes = self.validated_data.get(notes_key, slot_availability.notes)
                    slot_availability.save()
                
                created_slots.append(slot_availability)
        
        return created_slots


class UserAvailabilitySerializer(serializers.ModelSerializer):
    repeat_schedule_display = serializers.CharField(source='get_repeat_schedule_display', read_only=True)
    available_time_slots = serializers.SerializerMethodField()
    all_time_slots_with_status = serializers.SerializerMethodField()
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    
    # Individual time slot status displays
    morning_status_display = serializers.CharField(source='get_morning_status_display', read_only=True)
    afternoon_status_display = serializers.CharField(source='get_afternoon_status_display', read_only=True)
    evening_status_display = serializers.CharField(source='get_evening_status_display', read_only=True)
    night_status_display = serializers.CharField(source='get_night_status_display', read_only=True)
    
    class Meta:
        model = UserAvailability
        fields = [
            'id',
            # Morning slot
            'morning_available', 'morning_status', 'morning_status_display',
            # Afternoon slot
            'afternoon_available', 'afternoon_status', 'afternoon_status_display',
            # Evening slot
            'evening_available', 'evening_status', 'evening_status_display',
            # Night slot
            'night_available', 'night_status', 'night_status_display',
            # Other fields
            'available_time_slots', 'all_time_slots_with_status', 'repeat_schedule', 
            'repeat_schedule_display', 'start_date', 'end_date', 'notes', 
            'user_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_available_time_slots(self, obj):
        return obj.get_available_time_slots()
    
    def get_all_time_slots_with_status(self, obj):
        return obj.get_all_time_slots_with_status()
    
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class MonthAvailabilitySerializer(serializers.Serializer):
    """Serializer for month availability view with URL parameters"""
    year = serializers.IntegerField()
    month = serializers.IntegerField(min_value=1, max_value=12)
    user_id = serializers.IntegerField(required=False)
    
    def validate(self, data):
        year = data['year']
        month = data['month']
        
        # Validate that the date is reasonable
        current_year = datetime.now().year
        if year < current_year - 1 or year > current_year + 5:
            raise serializers.ValidationError("Invalid year range")
        
        return data


class QuickAvailabilityUpdateSerializer(serializers.Serializer):
    """Serializer for quick availability updates with individual time slot status"""
    date = serializers.DateField()
    
    # Individual time slots with their own status
    morning_available = serializers.BooleanField(default=False)
    morning_status = serializers.ChoiceField(choices=AvailabilityStatus.choices, default='available')
    
    afternoon_available = serializers.BooleanField(default=False)
    afternoon_status = serializers.ChoiceField(choices=AvailabilityStatus.choices, default='available')
    
    evening_available = serializers.BooleanField(default=False)
    evening_status = serializers.ChoiceField(choices=AvailabilityStatus.choices, default='available')
    
    night_available = serializers.BooleanField(default=False)
    night_status = serializers.ChoiceField(choices=AvailabilityStatus.choices, default='available')
    
    notes = serializers.CharField(required=False, allow_blank=True)
    
    def save(self):
        user = self.context['request'].user
        date = self.validated_data['date']
        
        # Create or update availability for this specific date
        availability, created = UserAvailability.objects.get_or_create(
            user=user,
            start_date=date,
            end_date=date,
            repeat_schedule=RepeatType.ONCE,
            defaults={
                'morning_available': self.validated_data['morning_available'],
                'morning_status': self.validated_data['morning_status'],
                'afternoon_available': self.validated_data['afternoon_available'],
                'afternoon_status': self.validated_data['afternoon_status'],
                'evening_available': self.validated_data['evening_available'],
                'evening_status': self.validated_data['evening_status'],
                'night_available': self.validated_data['night_available'],
                'night_status': self.validated_data['night_status'],
                'notes': self.validated_data.get('notes', '')
            }
        )
        
        if not created:
            # Update existing
            availability.morning_available = self.validated_data['morning_available']
            availability.morning_status = self.validated_data['morning_status']
            availability.afternoon_available = self.validated_data['afternoon_available']
            availability.afternoon_status = self.validated_data['afternoon_status']
            availability.evening_available = self.validated_data['evening_available']
            availability.evening_status = self.validated_data['evening_status']
            availability.night_available = self.validated_data['night_available']
            availability.night_status = self.validated_data['night_status']
            availability.notes = self.validated_data.get('notes', availability.notes)
            availability.save()
        
        return availability
