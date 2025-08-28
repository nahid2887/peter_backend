from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()


class EventType(models.TextChoices):
    OPEN = 'open', 'Open Invite'
    DIRECT = 'direct', 'Direct Invite'


class EventResponseChoice(models.TextChoices):
    GOING = 'going', 'Going'
    NOT_GOING = 'not_going', 'Not Going'
    PENDING = 'pending', 'Pending'


class RideRequestStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    ACCEPTED = 'accepted', 'Accepted'
    DECLINED = 'declined', 'Declined'
    COMPLETED = 'completed', 'Completed'


class Event(models.Model):
    """Main Event model"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    
    # Date and time
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField(blank=True, null=True)
    
    # Location
    location = models.CharField(max_length=500)
    
    # Event type and host
    event_type = models.CharField(max_length=20, choices=EventType.choices, default=EventType.OPEN)
    host = models.ForeignKey(User, on_delete=models.CASCADE, related_name='hosted_events')
    
    # Google Calendar integration
    add_to_google_calendar = models.BooleanField(default=False)
    google_calendar_event_id = models.CharField(max_length=255, blank=True, null=True)
    
    # Ride sharing
    ride_needed_for_event = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.date}"
    
    def get_going_count(self):
        """Get count of people going to the event"""
        return self.responses.filter(response=EventResponseChoice.GOING).count()
    
    def get_not_going_count(self):
        """Get count of people not going to the event"""
        return self.responses.filter(response=EventResponseChoice.NOT_GOING).count()
    
    def get_pending_count(self):
        """Get count of pending responses"""
        return self.responses.filter(response=EventResponseChoice.PENDING).count()
    
    def get_ride_requests(self):
        """Get all ride requests for this event"""
        return self.ride_requests.all()
    
    def get_available_ride_offers(self):
        """Get all available ride offers for this event"""
        return self.ride_offers.filter(is_available=True)


class EventInvite(models.Model):
    """Event invitations for direct invite events"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='invites')
    invitee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='event_invites')
    invited_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_invites')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['event', 'invitee']
    
    def __str__(self):
        return f"Invite to {self.event.title} for {self.invitee.full_name}"


class EventResponse(models.Model):
    """User responses to events"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='responses')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='event_responses')
    response = models.CharField(max_length=20, choices=EventResponseChoice.choices, default=EventResponseChoice.PENDING)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['event', 'user']
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"{self.user.full_name} - {self.event.title} ({self.get_response_display()})"


class RideRequest(models.Model):
    """Ride requests for events"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='ride_requests')
    requester = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ride_requests')
    
    # Ride details
    pickup_location = models.CharField(max_length=500, blank=True, null=True)
    special_instructions = models.TextField(blank=True, null=True)
    
    # Status
    status = models.CharField(max_length=20, choices=RideRequestStatus.choices, default=RideRequestStatus.PENDING)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Ride request by {self.requester.full_name} for {self.event.title}"


class RideOffer(models.Model):
    """Ride offers for events"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='ride_offers')
    driver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ride_offers')
    
    # Offer details
    available_seats = models.IntegerField(default=1)
    pickup_area = models.CharField(max_length=500, help_text="General area where you can pick up")
    drop_off_details = models.TextField(blank=True, null=True, help_text="Any specific drop-off instructions")
    
    # Availability
    is_available = models.BooleanField(default=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Ride offer by {self.driver.full_name} for {self.event.title}"
    
    def get_accepted_requests(self):
        """Get all accepted ride requests for this offer"""
        return self.accepted_requests.filter(status=RideRequestStatus.ACCEPTED)
    
    def get_available_seats_count(self):
        """Get remaining available seats"""
        accepted_count = self.get_accepted_requests().count()
        return max(0, self.available_seats - accepted_count)


class RideMatch(models.Model):
    """Matches between ride requests and offers"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ride_request = models.OneToOneField(RideRequest, on_delete=models.CASCADE, related_name='ride_match')
    ride_offer = models.ForeignKey(RideOffer, on_delete=models.CASCADE, related_name='accepted_requests')
    
    # Match status
    status = models.CharField(max_length=20, choices=RideRequestStatus.choices, default=RideRequestStatus.ACCEPTED)
    
    # Driver notes
    driver_notes = models.TextField(blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Ride match: {self.ride_request.requester.full_name} with {self.ride_offer.driver.full_name}"
