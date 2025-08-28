from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Event, EventInvite, EventResponse, RideRequest, RideOffer, RideMatch

User = get_user_model()


class UserBasicSerializer(serializers.ModelSerializer):
    """Basic user serializer for nested representations"""
    profile_photo_url = serializers.SerializerMethodField()
    children_names = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'email', 'full_name', 'profile_photo_url', 'children_names']
    
    def get_profile_photo_url(self, obj):
        """Get the full URL for the user's profile photo"""
        if obj.profile_photo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.profile_photo.url)
            return obj.profile_photo.url
        return None
    
    def get_children_names(self, obj):
        """Get list of children names for the user"""
        try:
            if hasattr(obj, 'profile') and obj.profile:
                children = obj.profile.children.all()
                return [child.name for child in children]
            return []
        except:
            return []


class EventResponseSerializer(serializers.ModelSerializer):
    user = UserBasicSerializer(read_only=True)
    response_display = serializers.CharField(source='get_response_display', read_only=True)
    
    class Meta:
        model = EventResponse
        fields = ['id', 'user', 'response', 'response_display', 'created_at', 'updated_at']


class EventInviteSerializer(serializers.ModelSerializer):
    invitee = UserBasicSerializer(read_only=True)
    invited_by = UserBasicSerializer(read_only=True)
    
    class Meta:
        model = EventInvite
        fields = ['id', 'invitee', 'invited_by', 'created_at']


class RideRequestSerializer(serializers.ModelSerializer):
    requester = UserBasicSerializer(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = RideRequest
        fields = ['id', 'requester', 'pickup_location', 'special_instructions', 
                 'status', 'status_display', 'created_at', 'updated_at']


class RideOfferSerializer(serializers.ModelSerializer):
    driver = UserBasicSerializer(read_only=True)
    available_seats_count = serializers.IntegerField(source='get_available_seats_count', read_only=True)
    
    class Meta:
        model = RideOffer
        fields = ['id', 'driver', 'available_seats', 'available_seats_count', 
                 'pickup_area', 'drop_off_details', 'is_available', 'created_at', 'updated_at']


class RideMatchSerializer(serializers.ModelSerializer):
    ride_request = RideRequestSerializer(read_only=True)
    ride_offer = RideOfferSerializer(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = RideMatch
        fields = ['id', 'ride_request', 'ride_offer', 'status', 'status_display', 
                 'driver_notes', 'created_at', 'updated_at']


class EventSerializer(serializers.ModelSerializer):
    host = UserBasicSerializer(read_only=True)
    event_type_display = serializers.CharField(source='get_event_type_display', read_only=True)
    responses = serializers.SerializerMethodField()
    invites = EventInviteSerializer(many=True, read_only=True)
    ride_requests = RideRequestSerializer(many=True, read_only=True)
    ride_offers = RideOfferSerializer(many=True, read_only=True)
    
    # Statistics
    going_count = serializers.SerializerMethodField()
    not_going_count = serializers.IntegerField(source='get_not_going_count', read_only=True)
    pending_count = serializers.IntegerField(source='get_pending_count', read_only=True)
    
    class Meta:
        model = Event
        fields = ['id', 'title', 'description', 'date', 'start_time', 'end_time', 
                 'location', 'event_type', 'event_type_display', 'host', 
                 'add_to_google_calendar', 'ride_needed_for_event', 
                 'responses', 'invites', 'ride_requests', 'ride_offers',
                 'going_count', 'not_going_count', 'pending_count',
                 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at', 'google_calendar_event_id']
    
    def get_responses(self, obj):
        """Get responses with host first, then other participants"""
        # Get all non-host responses
        participant_responses = obj.responses.exclude(user=obj.host).select_related('user').order_by('created_at')
        
        # Create a synthetic host response (host is always considered going)
        host_response_data = {
            'id': None,  # Host doesn't have a real response record
            'user': UserBasicSerializer(obj.host, context=self.context).data,
            'response': 'going',
            'response_display': 'Going',
            'created_at': obj.created_at.isoformat(),  # Use event creation time
            'updated_at': obj.updated_at.isoformat()
        }
        
        # Serialize participant responses
        participant_responses_data = EventResponseSerializer(participant_responses, many=True, context=self.context).data
        
        # Return host first, then participants
        return [host_response_data] + participant_responses_data
    
    def get_going_count(self, obj):
        """Get going count including the host (who is always considered going)"""
        participant_going_count = obj.responses.filter(response='going').exclude(user=obj.host).count()
        return participant_going_count + 1  # +1 for the host who is always going


class EventCreateSerializer(serializers.ModelSerializer):
    """Simplified serializer for creating events"""
    invitees = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        help_text="List of user IDs to invite (for direct invite events only)"
    )
    
    class Meta:
        model = Event
        fields = ['title', 'description', 'date', 'start_time', 'end_time', 
                 'location', 'event_type', 'add_to_google_calendar', 
                 'ride_needed_for_event', 'invitees']
    
    def create(self, validated_data):
        from .notification_service import create_event_invite_notification
        invitees = validated_data.pop('invitees', [])
        user = self.context['request'].user

        # Create the event
        event = Event.objects.create(
            host=user,
            **validated_data
        )

        # Create invites and auto-responses for direct invite events
        if event.event_type == 'direct' and invitees:
            invites = []
            responses = []

            for invitee_id in invitees:
                try:
                    invitee = User.objects.get(id=invitee_id)

                    # Create invite
                    invite = EventInvite(
                        event=event,
                        invitee=invitee,
                        invited_by=user
                    )
                    invites.append(invite)

                    # Send notification to invitee (except host)
                    if invitee != user:
                        create_event_invite_notification(event, invitee, user)

                    # Auto-create "going" response for invited user (but not for host)
                    if invitee != user:
                        responses.append(EventResponse(
                            event=event,
                            user=invitee,
                            response='going'
                        ))

                except User.DoesNotExist:
                    continue

            if invites:
                EventInvite.objects.bulk_create(invites)

            if responses:
                EventResponse.objects.bulk_create(responses)

        return event


class EventResponseCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating event responses"""
    
    class Meta:
        model = EventResponse
        fields = ['response']
    
    def create(self, validated_data):
        user = self.context['request'].user
        event_id = self.context['event_id']
        
        response, created = EventResponse.objects.update_or_create(
            event_id=event_id,
            user=user,
            defaults=validated_data
        )
        return response


class RideRequestCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating ride requests"""
    
    class Meta:
        model = RideRequest
        fields = ['pickup_location', 'special_instructions']
    
    def create(self, validated_data):
        user = self.context['request'].user
        event_id = self.context['event_id']
        
        ride_request = RideRequest.objects.create(
            event_id=event_id,
            requester=user,
            **validated_data
        )
        return ride_request


class RideOfferCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating ride offers"""
    
    class Meta:
        model = RideOffer
        fields = ['available_seats', 'pickup_area', 'drop_off_details']
    
    def create(self, validated_data):
        user = self.context['request'].user
        event_id = self.context['event_id']
        
        ride_offer = RideOffer.objects.create(
            event_id=event_id,
            driver=user,
            **validated_data
        )
        return ride_offer
