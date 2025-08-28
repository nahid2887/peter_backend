from rest_framework import permissions


class EventPermission(permissions.BasePermission):
    """
    Custom permission for Event objects:
    - Anyone can view events they have access to
    - Only event creators can create, update, or delete events
    - Anyone can respond to events or manage ride requests/offers
    """
    
    def has_permission(self, request, view):
        # Must be authenticated
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Allow all authenticated users to perform actions
        return True
    
    def has_object_permission(self, request, view, obj):
        # Read permissions for everyone who can see the event
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Custom actions (respond, request_ride, etc.) are allowed for everyone
        if view.action in ['respond', 'request_ride', 'offer_ride', 'accept_ride_request']:
            return True
        
        # Write permissions only for event creator
        if view.action in ['update', 'partial_update', 'destroy']:
            return obj.host == request.user
        
        return False


class RideRequestPermission(permissions.BasePermission):
    """
    Custom permission for RideRequest objects:
    - Only the requester can view, update, or delete their own ride requests
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return True
    
    def has_object_permission(self, request, view, obj):
        # Only the requester can access their ride request
        return obj.requester == request.user


class RideOfferPermission(permissions.BasePermission):
    """
    Custom permission for RideOffer objects:
    - Only the driver can view, update, or delete their own ride offers
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return True
    
    def has_object_permission(self, request, view, obj):
        # Only the driver can access their ride offer
        return obj.driver == request.user
