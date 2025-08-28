from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db import models
from django.utils import timezone
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .models import Event, EventResponse, RideRequest, RideOffer, RideMatch
from .serializers import (
    EventSerializer, EventCreateSerializer, EventResponseSerializer, 
    EventResponseCreateSerializer, RideRequestSerializer, RideRequestCreateSerializer,
    RideOfferSerializer, RideOfferCreateSerializer, RideMatchSerializer
)
from .permissions import EventPermission, RideRequestPermission, RideOfferPermission

# Swagger response schemas
event_list_response = openapi.Response(
    description="List of events",
    schema=openapi.Schema(
        type=openapi.TYPE_ARRAY,
        items=openapi.Schema(type=openapi.TYPE_OBJECT)
    )
)

event_detail_response = openapi.Response(
    description="Event details",
    schema=openapi.Schema(type=openapi.TYPE_OBJECT)
)

error_response = openapi.Response(
    description="Error response",
    schema=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'detail': openapi.Schema(type=openapi.TYPE_STRING),
            'error': openapi.Schema(type=openapi.TYPE_STRING),
        }
    )
)

# Event Views
@swagger_auto_schema(
    method='get',
    operation_description="Get list of events with optional filtering",
    manual_parameters=[
        openapi.Parameter(
            'event_type', 
            openapi.IN_QUERY, 
            description="Filter by event type (open/direct)", 
            type=openapi.TYPE_STRING,
            enum=['open', 'direct']
        ),
        openapi.Parameter(
            'start_date', 
            openapi.IN_QUERY, 
            description="Filter events from this date (YYYY-MM-DD)", 
            type=openapi.TYPE_STRING,
            format=openapi.FORMAT_DATE
        ),
        openapi.Parameter(
            'end_date', 
            openapi.IN_QUERY, 
            description="Filter events until this date (YYYY-MM-DD)", 
            type=openapi.TYPE_STRING,
            format=openapi.FORMAT_DATE
        ),
    ],
    responses={
        200: event_list_response,
        401: error_response,
    },
    tags=['Events']
)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def event_list(request):
    """Get list of events with optional filtering"""
    queryset = Event.objects.all().select_related('host').prefetch_related(
        'responses__user', 'invites__invitee', 'ride_requests__requester', 'ride_offers__driver'
    )
    
    # Filter by event type
    event_type = request.query_params.get('event_type', None)
    if event_type:
        queryset = queryset.filter(event_type=event_type)
    
    # Filter by date range
    start_date = request.query_params.get('start_date', None)
    end_date = request.query_params.get('end_date', None)
    if start_date:
        queryset = queryset.filter(date__gte=start_date)
    if end_date:
        queryset = queryset.filter(date__lte=end_date)
    
    # For direct invite events, only show events user is invited to or hosting
    user = request.user
    queryset = queryset.filter(
        models.Q(event_type='open') |  # All open events
        models.Q(host=user) |  # Events user is hosting
        models.Q(invites__invitee=user)  # Events user is invited to
    ).distinct().order_by('date', 'start_time')
    
    serializer = EventSerializer(queryset, many=True, context={'request': request})
    return Response(serializer.data)

@swagger_auto_schema(
    method='post',
    operation_description="Create a new event",
    request_body=EventCreateSerializer,
    responses={
        201: event_detail_response,
        400: error_response,
        401: error_response,
    },
    tags=['Events']
)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def event_create(request):
    """Create a new event"""
    serializer = EventCreateSerializer(data=request.data, context={'request': request})
    
    if serializer.is_valid():
        event = serializer.save()
        return Response(EventSerializer(event, context={'request': request}).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@swagger_auto_schema(
    method='get',
    operation_description="Get event details by ID",
    responses={
        200: event_detail_response,
        404: error_response,
        401: error_response,
    },
    tags=['Events']
)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def event_detail(request, event_id):
    """Get event details by ID"""
    event = get_object_or_404(Event, id=event_id)
    
    # Check if user has permission to view this event
    user = request.user
    if event.event_type == 'direct':
        if not (event.host == user or event.invites.filter(invitee=user).exists()):
            raise PermissionDenied("You don't have permission to view this event")
    
    serializer = EventSerializer(event, context={'request': request})
    return Response(serializer.data)

@swagger_auto_schema(
    method='put',
    operation_description="Update an event (only event creator)",
    request_body=EventCreateSerializer,
    responses={
        200: event_detail_response,
        400: error_response,
        401: error_response,
        403: error_response,
        404: error_response,
    },
    tags=['Events']
)
@api_view(['PUT'])
@permission_classes([permissions.IsAuthenticated])
def event_update(request, event_id):
    """Update an event (only event creator)"""
    event = get_object_or_404(Event, id=event_id)
    
    # Check if user is the event creator
    if event.host != request.user:
        raise PermissionDenied("Only the event creator can update this event")
    
    serializer = EventCreateSerializer(event, data=request.data, context={'request': request})
    
    if serializer.is_valid():
        event = serializer.save()
        return Response(EventSerializer(event, context={'request': request}).data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@swagger_auto_schema(
    method='delete',
    operation_description="Delete an event (only event creator)",
    responses={
        204: openapi.Response(description="Event deleted successfully"),
        401: error_response,
        403: error_response,
        404: error_response,
    },
    tags=['Events']
)
@api_view(['DELETE'])
@permission_classes([permissions.IsAuthenticated])
def event_delete(request, event_id):
    """Delete an event (only event creator)"""
    event = get_object_or_404(Event, id=event_id)
    
    # Check if user is the event creator
    if event.host != request.user:
        raise PermissionDenied("Only the event creator can delete this event")
    
    event.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)

@swagger_auto_schema(
    method='post',
    operation_description="Respond to an event (going/not going)",
    request_body=EventResponseCreateSerializer,
    responses={
        200: openapi.Response(
            description="Event response created/updated",
            schema=openapi.Schema(type=openapi.TYPE_OBJECT)
        ),
        400: error_response,
        401: error_response,
        404: error_response,
    },
    tags=['Events']
)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def event_respond(request, event_id):
    """Respond to an event (going/not going)"""
    event = get_object_or_404(Event, id=event_id)
    
    # Check if user has permission to respond to this event
    user = request.user
    
    # Host cannot respond to their own event (they are automatically considered going)
    if event.host == user:
        return Response(
            {"detail": "Host cannot respond to their own event. You are automatically considered as going."}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if event.event_type == 'direct':
        if not event.invites.filter(invitee=user).exists():
            raise PermissionDenied("You don't have permission to respond to this event")
    
    serializer = EventResponseCreateSerializer(
        data=request.data,
        context={'request': request, 'event_id': event.id}
    )
    
    if serializer.is_valid():
        response = serializer.save()
        
        # For direct invite events: if user responds "not_going", remove them from invites
        if (event.event_type == 'direct' and 
            response.response == 'not_going' and 
            event.invites.filter(invitee=user).exists()):
            
            # Remove the invite
            event.invites.filter(invitee=user).delete()
            
            # Also delete the response since they're no longer invited
            response.delete()
            
            return Response(
                {"detail": "You have declined the invitation and been removed from the event"}, 
                status=status.HTTP_200_OK
            )
        
        return Response(EventResponseSerializer(response, context={'request': request}).data, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@swagger_auto_schema(
    method='get',
    operation_description="Get all responses for an event",
    responses={
        200: openapi.Response(
            description="List of event responses",
            schema=openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Schema(type=openapi.TYPE_OBJECT)
            )
        ),
        401: error_response,
        404: error_response,
    },
    tags=['Events']
)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def event_responses(request, event_id):
    """Get all responses for an event"""
    event = get_object_or_404(Event, id=event_id)
    
    # Check if user has permission to view responses
    user = request.user
    if event.event_type == 'direct':
        if not (event.host == user or event.invites.filter(invitee=user).exists()):
            raise PermissionDenied("You don't have permission to view responses for this event")
    
    responses = EventResponse.objects.filter(event=event).select_related('user')
    serializer = EventResponseSerializer(responses, many=True)
    return Response(serializer.data)

@swagger_auto_schema(
    method='get',
    operation_description="Get events where user is hosting, invited to, or has responded 'going'",
    responses={
        200: event_list_response,
        401: error_response,
    },
    tags=['Events']
)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def my_events(request):
    """Get events where user is hosting, invited to, or has responded 'going'"""
    user = request.user
    
    # Get events where:
    # 1. User is the host (events they created/host)
    # 2. User is invited to (direct invite events) - excludes declined invitations
    # 3. User has responded 'going' to (events they're attending)
    my_events = Event.objects.filter(
        models.Q(host=user) |  # Events user is hosting/created
        models.Q(invites__invitee=user) |  # Events user is invited to (not declined)
        models.Q(
            responses__user=user,  # User has responded
            responses__response='going'  # User is going
        )
    ).distinct().select_related('host').prefetch_related(
        'responses__user', 'invites__invitee', 'ride_requests__requester', 'ride_offers__driver'
    ).order_by('date', 'start_time')
    
    serializer = EventSerializer(my_events, many=True, context={'request': request})
    return Response(serializer.data)

@swagger_auto_schema(
    method='get',
    operation_description="Get upcoming events only",
    responses={
        200: event_list_response,
        401: error_response,
    },
    tags=['Events']
)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def upcoming_events(request):
    """Get upcoming events"""
    today = timezone.now().date()
    user = request.user
    
    queryset = Event.objects.filter(date__gte=today).filter(
        models.Q(event_type='open') |  # All open events
        models.Q(host=user) |  # Events user is hosting
        models.Q(invites__invitee=user)  # Events user is invited to
    ).distinct().select_related('host').prefetch_related(
        'responses__user', 'invites__invitee', 'ride_requests__requester', 'ride_offers__driver'
    ).order_by('date', 'start_time')
    
    serializer = EventSerializer(queryset, many=True, context={'request': request})
    return Response(serializer.data)

# Ride Request Views
@swagger_auto_schema(
    method='post',
    operation_description="Request a ride for an event",
    request_body=RideRequestCreateSerializer,
    responses={
        201: openapi.Response(
            description="Ride request created",
            schema=openapi.Schema(type=openapi.TYPE_OBJECT)
        ),
        400: error_response,
        401: error_response,
        404: error_response,
    },
    tags=['Ride Requests']
)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def ride_request_create(request, event_id):
    """Request a ride for an event"""
    event = get_object_or_404(Event, id=event_id)
    user = request.user
    
    # Check if user has permission to request ride for this event
    # User must be: hosting, invited and going, or responded going to open events
    has_permission = False
    
    # Check if user is hosting the event
    if event.host == user:
        has_permission = True
    
    # For direct invite events: user must be invited AND not have declined
    elif event.event_type == 'direct' and event.invites.filter(invitee=user).exists():
        # Check if user hasn't explicitly responded "not_going"
        user_response = event.responses.filter(user=user).first()
        if not user_response or user_response.response != 'not_going':
            has_permission = True
    
    # For open events: user must have responded 'going'
    elif event.event_type == 'open' and event.responses.filter(user=user, response='going').exists():
        has_permission = True
    
    if not has_permission:
        raise PermissionDenied("You must be hosting this event or be an accepted invitee to request a ride")
    
    # Check if user already has a ride request for this event
    existing_request = RideRequest.objects.filter(
        event=event,
        requester=request.user
    ).first()
    
    if existing_request:
        return Response(
            {"detail": "You already have a ride request for this event"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    serializer = RideRequestCreateSerializer(
        data=request.data,
        context={'request': request, 'event_id': event.id}
    )
    
    if serializer.is_valid():
        ride_request = serializer.save()
        return Response(RideRequestSerializer(ride_request).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@swagger_auto_schema(
    method='get',
    operation_description="Get ride requests for a specific event (only for event attendees)",
    responses={
        200: openapi.Response(
            description="List of ride requests for the event",
            schema=openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Schema(type=openapi.TYPE_OBJECT)
            )
        ),
        401: error_response,
        403: error_response,
        404: error_response,
    },
    tags=['Ride Requests']
)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def event_ride_requests(request, event_id):
    """Get ride requests for a specific event (only for event attendees)"""
    event = get_object_or_404(Event, id=event_id)
    user = request.user
    
    # Check if user has permission to view ride requests for this event
    # User must be:
    # 1. The event host, OR
    # 2. Going to the event (for open events) OR
    # 3. Invited and going to the event (for direct events)
    
    if event.host != user:
        # Check if user has access to the event first
        if event.event_type == 'direct':
            if not event.invites.filter(invitee=user).exists():
                raise PermissionDenied("You don't have permission to view this event")
        
        # Check if user is going to the event
        user_response = event.responses.filter(user=user).first()
        if not user_response or user_response.response != 'going':
            raise PermissionDenied("You must be attending this event to view ride requests")
    
    # Get all ride requests for this event
    ride_requests = RideRequest.objects.filter(
        event=event
    ).select_related('requester').order_by('-created_at')
    
    serializer = RideRequestSerializer(ride_requests, many=True)
    return Response(serializer.data)

@swagger_auto_schema(
    method='get',
    operation_description="Get list of user's ride requests",
    responses={
        200: openapi.Response(
            description="List of ride requests",
            schema=openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Schema(type=openapi.TYPE_OBJECT)
            )
        ),
        401: error_response,
    },
    tags=['Ride Requests']
)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def ride_request_list(request):
    """Get list of user's ride requests"""
    ride_requests = RideRequest.objects.filter(
        requester=request.user
    ).select_related('event', 'requester').order_by('-created_at')
    
    serializer = RideRequestSerializer(ride_requests, many=True)
    return Response(serializer.data)

@swagger_auto_schema(
    method='get',
    operation_description="Get ride request details",
    responses={
        200: openapi.Response(
            description="Ride request details",
            schema=openapi.Schema(type=openapi.TYPE_OBJECT)
        ),
        401: error_response,
        403: error_response,
        404: error_response,
    },
    tags=['Ride Requests']
)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def ride_request_detail(request, request_id):
    """Get ride request details (only if user is attending the event)"""
    ride_request = get_object_or_404(RideRequest, id=request_id)
    event = ride_request.event
    user = request.user
    
    # Check if user has permission to view this ride request
    # User must be:
    # 1. The event host, OR
    # 2. The requester themselves, OR  
    # 3. Going to the event (for open events) OR
    # 4. Invited and going to the event (for direct events)
    
    if event.host != user and ride_request.requester != user:
        # Check if user has access to the event first
        if event.event_type == 'direct':
            if not event.invites.filter(invitee=user).exists():
                raise PermissionDenied("You don't have permission to view this event")
        
        # Check if user is going to the event
        user_response = event.responses.filter(user=user).first()
        if not user_response or user_response.response != 'going':
            raise PermissionDenied("You must be attending this event to view ride request details")
    
    serializer = RideRequestSerializer(ride_request)
    return Response(serializer.data)

@swagger_auto_schema(
    method='post',
    operation_description="Cancel a ride request (only if user is attending the event)",
    responses={
        200: openapi.Response(
            description="Ride request cancelled",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={'detail': openapi.Schema(type=openapi.TYPE_STRING)}
            )
        ),
        401: error_response,
        403: error_response,
        404: error_response,
    },
    tags=['Ride Requests']
)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def ride_request_cancel(request, request_id):
    """Cancel a ride request (only if user is attending the event)"""
    ride_request = get_object_or_404(RideRequest, id=request_id)
    event = ride_request.event
    user = request.user
    
    # Check if user has permission to cancel this ride request
    # User must be:
    # 1. The requester themselves (can always cancel their own request), OR
    # 2. The event host (can cancel any request for their event)
    # AND the user must be attending the event (except for the requester who can always cancel their own)
    
    if ride_request.requester != user:
        # If not the requester, check if they're the event host
        if event.host != user:
            raise PermissionDenied("You can only cancel your own ride requests or requests for events you host")
    
    # For anyone cancelling (including requester), check event attendance
    # Exception: The requester can always cancel their own request even if not attending
    if ride_request.requester != user:
        # Check if user has access to the event first
        if event.event_type == 'direct':
            if not event.invites.filter(invitee=user).exists():
                raise PermissionDenied("You don't have permission to access this event")
        
        # Check if user is going to the event
        user_response = event.responses.filter(user=user).first()
        if not user_response or user_response.response != 'going':
            raise PermissionDenied("You must be attending this event to cancel ride requests")
    
    # Check if there's an existing match
    if hasattr(ride_request, 'ride_match'):
        ride_match = ride_request.ride_match
        ride_match.delete()
    
    ride_request.status = 'declined'
    ride_request.save()
    
    return Response({"detail": "Ride request cancelled"}, status=status.HTTP_200_OK)

# ==============================================================================
# RIDE OFFER VIEWS - COMMENTED OUT (SIMPLIFIED SYSTEM - NO LONGER NEEDED)
# ==============================================================================
# The system has been simplified to work without ride offers. 
# Users only send ride requests, and other users can accept them directly.
# This eliminates the complexity of managing separate ride offers.
# 
# If you need to restore ride offers in the future, uncomment the code below.
# ==============================================================================

# # Ride Offer Views
# @swagger_auto_schema(
#     method='post',
#     operation_description="Offer a ride for an event",
#     request_body=RideOfferCreateSerializer,
#     responses={
#         201: openapi.Response(
#             description="Ride offer created",
#             schema=openapi.Schema(type=openapi.TYPE_OBJECT)
#         ),
#         400: error_response,
#         401: error_response,
#         404: error_response,
#     },
#     tags=['Ride Offers']
# )
# @api_view(['POST'])
# @permission_classes([permissions.IsAuthenticated])
# def ride_offer_create(request, event_id):
#     """Offer a ride for an event"""
#     [... COMMENTED OUT - SEE ABOVE EXPLANATION ...]

# [Additional ride offer functions commented out...]
# def ride_offer_list, ride_offer_detail, ride_offer_accept, ride_offer_cancel

# All ride offer functions have been commented out to simplify the system.
# The new simplified system works as follows:
# 1. Users create ride requests when they need a ride
# 2. Other users can directly accept those ride requests 
# 3. No need to create separate ride offers first

@swagger_auto_schema(
    method='post',
    operation_description="Accept a ride request (simplified - no ride offer needed)",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'driver_notes': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='Optional notes from the driver'
            ),
            'available_seats': openapi.Schema(
                type=openapi.TYPE_INTEGER,
                description='Number of seats available in your car (default: 1)',
                default=1
            ),
            'pickup_area': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='General area where you can pick up',
                default='Will coordinate pickup location'
            )
        }
    ),
    responses={
        201: openapi.Response(
            description="Ride request accepted",
            schema=openapi.Schema(type=openapi.TYPE_OBJECT)
        ),
        400: error_response,
        401: error_response,
        403: error_response,
        404: error_response,
    },
    tags=['Ride Requests']
)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def accept_ride_request(request, request_id):
    """Accept a ride request (simplified - no ride offer needed)"""
    ride_request = get_object_or_404(RideRequest, id=request_id)
    event = ride_request.event
    user = request.user
    
    # Check if user has permission to accept ride requests for this event
    # User must be:
    # 1. Going to the event (for open events) OR
    # 2. Invited and going to the event (for direct events)
    # 3. Not the requester themselves
    
    if ride_request.requester == user:
        return Response(
            {"detail": "You cannot accept your own ride request"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Check if user has access to the event first
    if event.event_type == 'direct':
        if not event.invites.filter(invitee=user).exists():
            raise PermissionDenied("You don't have permission to access this event")
    
    # Check if user is going to the event
    user_response = event.responses.filter(user=user).first()
    if not user_response or user_response.response != 'going':
        raise PermissionDenied("You must be attending this event to accept ride requests")
    
    # Check if ride request is already accepted
    if hasattr(ride_request, 'ride_match'):
        return Response(
            {"detail": "This ride request has already been accepted"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Get driver details from request
    driver_notes = request.data.get('driver_notes', '')
    available_seats = request.data.get('available_seats', 1)
    pickup_area = request.data.get('pickup_area', 'Will coordinate pickup location')
    
    # Create a temporary ride offer for this acceptance (to maintain existing structure)
    with transaction.atomic():
        # Create temporary ride offer
        ride_offer = RideOffer.objects.create(
            event=event,
            driver=user,
            available_seats=available_seats,
            pickup_area=pickup_area,
            drop_off_details=f"Accepting ride request from {ride_request.requester.full_name}",
            is_available=False  # Mark as not available since it's for this specific request
        )
        
        # Create the ride match
        ride_match = RideMatch.objects.create(
            ride_request=ride_request,
            ride_offer=ride_offer,
            driver_notes=driver_notes
        )
        
        # Update ride request status
        ride_request.status = 'accepted'
        ride_request.save()
    
    return Response({
        "id": str(ride_match.id),
        "ride_request": {
            "id": str(ride_request.id),
            "requester": {
                "id": str(ride_request.requester.id),
                "email": ride_request.requester.email,
                "full_name": ride_request.requester.full_name
            },
            "pickup_location": ride_request.pickup_location,
            "status": ride_request.status,
            "status_display": ride_request.get_status_display()
        },
        "driver": {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name
        },
        "status": "accepted",
        "status_display": "Accepted",
        "driver_notes": driver_notes,
        "available_seats": available_seats,
        "pickup_area": pickup_area,
        "created_at": ride_match.created_at.isoformat(),
        "updated_at": ride_match.updated_at.isoformat()
    }, status=status.HTTP_201_CREATED)
