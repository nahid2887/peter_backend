

from rest_framework import generics, status, viewsets
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date
from django.utils import timezone
from django.db import models
from datetime import datetime, timedelta
from calendar import monthrange
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from account.models import User
from .models import UserAvailability, TimeSlotAvailability
from .serializers import (
    UserAvailabilitySerializer,
    MonthAvailabilitySerializer,
    QuickAvailabilityUpdateSerializer,
    TimeSlotAvailabilitySerializer,
    MultipleTimeSlotSerializer
)
class UserAvailabilityViewSet(viewsets.ModelViewSet):
    """CRUD operations for user availability settings (legacy)"""
    serializer_class = UserAvailabilitySerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return UserAvailability.objects.filter(user=self.request.user)


class TimeSlotAvailabilityViewSet(viewsets.ModelViewSet):
    """CRUD operations for individual time slot availability"""
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return TimeSlotAvailability.objects.filter(user=self.request.user)


@swagger_auto_schema(
    method='get',
    manual_parameters=[
        openapi.Parameter('date', openapi.IN_QUERY, description="Date (YYYY-MM-DD)", type=openapi.TYPE_STRING, required=True),
    ],
    responses={200: 'Day availability data for group member'}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def group_member_day_availability(request, user_id):
    if serializer.is_valid():
        created_slots = serializer.save()
        return Response(
            TimeSlotAvailabilitySerializer(created_slots, many=True).data,
            status=status.HTTP_201_CREATED
        )
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='get',
    manual_parameters=[
        openapi.Parameter('year', openapi.IN_QUERY, description="Year", type=openapi.TYPE_INTEGER, required=True),
        openapi.Parameter('month', openapi.IN_QUERY, description="Month (1-12)", type=openapi.TYPE_INTEGER, required=True),
    ],
    responses={200: 'Month availability data with individual time slots'}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def month_time_slot_availability_view(request):
    """Get all time slot availability for a specific month"""
    try:
        year = int(request.GET.get('year'))
        month = int(request.GET.get('month'))
        
        # Always use the authenticated user
        user = request.user
        
        # Validate month
        if month < 1 or month > 12:
            return Response(
                {"error": "Month must be between 1 and 12"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get month availability data using new model
        month_data = TimeSlotAvailability.get_user_availability_for_month(user, year, month)
        
        return Response({
            'year': year,
            'month': month,
            'user': {
                'id': user.id,
                'name': user.full_name
            },
            'availability': month_data
        })
        
    except (ValueError, TypeError):
        return Response(
            {"error": "Invalid year or month parameter"}, 
            status=status.HTTP_400_BAD_REQUEST
        )


@swagger_auto_schema(
    method='get',
    manual_parameters=[
        openapi.Parameter('date', openapi.IN_QUERY, description="Date (YYYY-MM-DD)", type=openapi.TYPE_STRING, required=True),
    ],
    responses={200: 'Day availability data with individual time slots'}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def day_time_slot_availability_view(request):
    """Get individual time slot availability for a specific date"""
    try:
        date_str = request.GET.get('date')
        
        if not date_str:
            return Response(
                {"error": "Date parameter is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # Always use the authenticated user
        user = request.user
        
        # Get all time slot availabilities for this date
        availabilities = TimeSlotAvailability.get_user_availability_for_date(user, date)
        
        # Create a dictionary for quick lookup by slot type
        availability_dict = {av.slot_type: av for av in availabilities}
        
        # Get all possible time slot types
        from .models import TimeSlotType
        
        # Format the response with all time slot types
        time_slots = []
        for slot_type in TimeSlotType:
            if slot_type.value in availability_dict:
                # User has set availability for this slot
                availability = availability_dict[slot_type.value]
                slot_info = availability.get_time_slot_info()
                time_slots.append({
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
            else:
                # User hasn't set availability for this slot - show default
                slot_info = TimeSlotAvailability.get_time_slot_info_static(slot_type.value)
                time_slots.append({
                    'name': slot_info['name'],
                    'time': slot_info['time'],
                    'type': slot_type.value,
                    'status': 'available',  # Default status
                    'status_display': 'Available',
                    'repeat_schedule': None,
                    'repeat_schedule_display': None,
                    'notes': '',
                    'availability_id': None  # No record exists yet
                })
        
        return Response({
            'date': date,
            'day': date.day,
            'time_slots': time_slots,
            'total_available_slots': len([s for s in time_slots if s['status'] == 'available']),
            'total_busy_slots': len([s for s in time_slots if s['status'] == 'busy']),
            'total_slots': len(time_slots)
        })
        
    except ValueError:
        return Response(
            {"error": "Invalid date format. Use YYYY-MM-DD"}, 
            status=status.HTTP_400_BAD_REQUEST
        )


@swagger_auto_schema(
    method='get',
    manual_parameters=[
        openapi.Parameter('year', openapi.IN_QUERY, description="Year", type=openapi.TYPE_INTEGER, required=True),
        openapi.Parameter('month', openapi.IN_QUERY, description="Month (1-12)", type=openapi.TYPE_INTEGER, required=True),
    ],
    responses={200: 'Month availability data'}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def month_availability_view(request):
    """Get all availability for a specific month with URL parameters"""
    try:
        year = int(request.GET.get('year'))
        month = int(request.GET.get('month'))
        
        # Always use the authenticated user
        user = request.user
        
        # Validate month
        if month < 1 or month > 12:
            return Response(
                {"error": "Month must be between 1 and 12"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get month availability data
        month_data = UserAvailability.get_user_availability_for_month(user, year, month)
        
        return Response({
            'year': year,
            'month': month,
            'user': {
                'id': user.id,
                'name': user.full_name
            },
            'availability': month_data
        })
        
    except (ValueError, TypeError):
        return Response(
            {"error": "Invalid year or month parameter"}, 
            status=status.HTTP_400_BAD_REQUEST
        )


@swagger_auto_schema(
    method='post',
    request_body=QuickAvailabilityUpdateSerializer,
    responses={201: UserAvailabilitySerializer()}
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def quick_availability_update(request):
    """Quick update/create availability for a specific date"""
    serializer = QuickAvailabilityUpdateSerializer(data=request.data, context={'request': request})
    
    if serializer.is_valid():
        availability = serializer.save()
        return Response(
            UserAvailabilitySerializer(availability).data,
            status=status.HTTP_201_CREATED
        )
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='get',
    responses={200: UserAvailabilitySerializer(many=True)}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_availability_list(request):
    """Get all availability settings for the current user"""
    availabilities = UserAvailability.objects.filter(user=request.user)
    serializer = UserAvailabilitySerializer(availabilities, many=True)
    return Response(serializer.data)


@swagger_auto_schema(
    method='get',
    manual_parameters=[
        openapi.Parameter('date', openapi.IN_QUERY, description="Date (YYYY-MM-DD)", type=openapi.TYPE_STRING, required=True),
    ],
    responses={200: 'Day availability data'}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def day_availability_view(request):
    """Get availability for a specific date"""
    try:
        date_str = request.GET.get('date')
        
        if not date_str:
            return Response(
                {"error": "Date parameter is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # Always use the authenticated user
        user = request.user
        
        # Find availability settings that apply to this date
        availabilities = UserAvailability.objects.filter(
            user=user,
            start_date__lte=date,
            end_date__gte=date
        ).order_by('-created_at')
        
        day_info = {
            'date': date,
            'time_slots': [],
            'notes': None,
            'availability_id': None
        }
        
        # Find the most recent availability that applies
        all_time_slots = []
        availability_id = None
        notes = None
        
        # Collect all available time slots from all matching availability records
        for availability in availabilities:
            if availability.is_available_on_date(date):
                # Get all time slots with their status
                all_slots = availability.get_all_time_slots_with_status()
                for slot_type, slot_data in all_slots.items():
                    # Only include slots where available is True
                    if slot_data['available']:
                        # Check if this slot type is already added
                        slot_exists = any(slot['type'] == slot_type for slot in all_time_slots)
                        if not slot_exists:
                            all_time_slots.append({
                                'name': slot_data['name'],
                                'time': slot_data['time'],
                                'type': slot_type,
                                'status': slot_data['status'],
                                'status_display': slot_data['status_display']
                            })
                
                # Use the most recent availability's ID and notes
                if availability_id is None:
                    availability_id = availability.id
                    notes = availability.notes
        
        if all_time_slots:
            day_info.update({
                'time_slots': all_time_slots,
                'notes': notes,
                'availability_id': availability_id
            })
        
        return Response(day_info)
        
    except ValueError:
        return Response(
            {"error": "Invalid date format. Use YYYY-MM-DD"}, 
            status=status.HTTP_400_BAD_REQUEST
        )



#
# Simple endpoint: View another user's calendar for a specific date (no group membership required)
@swagger_auto_schema(
    method='get',
    manual_parameters=[
        openapi.Parameter('date', openapi.IN_QUERY, description="Date (YYYY-MM-DD)", type=openapi.TYPE_STRING, required=False),
    ],
    responses={200: 'Day availability data for user'}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_day_availability_view(request, user_id):
    """Get another user's calendar for a specific date (no group membership required)"""
    date_str = request.GET.get('date')
    if not date_str:
        # Default to today if not provided
        date = timezone.now().date()
    else:
        try:
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({"error": "Invalid date format. Use YYYY-MM-DD"}, status=status.HTTP_400_BAD_REQUEST)
    target_user = get_object_or_404(User, id=user_id)
    availabilities = UserAvailability.objects.filter(
        user=target_user,
        start_date__lte=date,
        end_date__gte=date
    ).order_by('-created_at')
    day_info = {
        'date': date,
        'user_id': target_user.id,
        'time_slots': [],
        'notes': None,
        'availability_id': None
    }
    all_time_slots = []
    availability_id = None
    notes = None
    for availability in availabilities:
        if availability.is_available_on_date(date):
            all_slots = availability.get_all_time_slots_with_status()
            for slot_type, slot_data in all_slots.items():
                if slot_data['available']:
                    slot_exists = any(slot['type'] == slot_type for slot in all_time_slots)
                    if not slot_exists:
                        all_time_slots.append({
                            'name': slot_data['name'],
                            'time': slot_data['time'],
                            'type': slot_type,
                            'status': slot_data['status'],
                            'status_display': slot_data['status_display']
                        })
            if availability_id is None:
                availability_id = availability.id
                notes = availability.notes
    if all_time_slots:
        day_info.update({
            'time_slots': all_time_slots,
            'notes': notes,
            'availability_id': availability_id
        })
    return Response(day_info)




#
# Endpoint: View another user's calendar for a specific month (no group membership required)
@swagger_auto_schema(
    method='get',
    manual_parameters=[
        openapi.Parameter('year', openapi.IN_QUERY, description="Year", type=openapi.TYPE_INTEGER, required=True),
        openapi.Parameter('month', openapi.IN_QUERY, description="Month (1-12)", type=openapi.TYPE_INTEGER, required=True),
    ],
    responses={200: 'Month availability data for user'}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_month_availability_view(request, user_id):
    """Get another user's calendar for a specific month (no group membership required)"""
    # Default to current year and month if not provided
    now = timezone.now()
    year = request.GET.get('year')
    month = request.GET.get('month')
    try:
        year = int(year) if year is not None else now.year
        month = int(month) if month is not None else now.month
        if month < 1 or month > 12:
            return Response({"error": "Month must be between 1 and 12"}, status=status.HTTP_400_BAD_REQUEST)
    except (ValueError, TypeError):
        return Response({"error": "Invalid year or month parameter"}, status=status.HTTP_400_BAD_REQUEST)

    target_user = get_object_or_404(User, id=user_id)
    # Get all availabilities for this user in the month
    from calendar import monthrange
    num_days = monthrange(year, month)[1]
    days = []
    for day in range(1, num_days + 1):
        date = datetime(year, month, day).date()
        availabilities = UserAvailability.objects.filter(
            user=target_user,
            start_date__lte=date,
            end_date__gte=date
        ).order_by('-created_at')
        day_info = {
            'date': date,
            'user_id': target_user.id,
            'time_slots': [],
            'notes': None,
            'availability_id': None
        }
        all_time_slots = []
        availability_id = None
        notes = None
        for availability in availabilities:
            if availability.is_available_on_date(date):
                all_slots = availability.get_all_time_slots_with_status()
                for slot_type, slot_data in all_slots.items():
                    if slot_data['available']:
                        slot_exists = any(slot['type'] == slot_type for slot in all_time_slots)
                        if not slot_exists:
                            all_time_slots.append({
                                'name': slot_data['name'],
                                'time': slot_data['time'],
                                'type': slot_type,
                                'status': slot_data['status'],
                                'status_display': slot_data['status_display']
                            })
                if availability_id is None:
                    availability_id = availability.id
                    notes = availability.notes
        if all_time_slots:
            day_info.update({
                'time_slots': all_time_slots,
                'notes': notes,
                'availability_id': availability_id
            })
        days.append(day_info)
    return Response({
        'year': year,
        'month': month,
        'user': {
            'id': target_user.id,
            'name': getattr(target_user, 'full_name', str(target_user))
        },
        'days': days
    })

