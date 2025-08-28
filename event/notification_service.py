from django.contrib.auth import get_user_model
from chat.models import Notification

User = get_user_model()

def create_event_invite_notification(event, invitee, invited_by):
    """
    Create a notification for the invitee when invited to an event.
    """
    title = f"You have been invited to {event.title}"
    message = f"{invited_by.full_name} has invited you to the event '{event.title}'."
    notification = Notification.objects.create(
        recipient=invitee,
        sender=invited_by,
        notification_type='group_add',  # Or define a new type like 'event_invite'
        title=title,
        message=message,
        extra_data={
            'event_id': str(event.id),
            'event_title': event.title,
            'invited_by': invited_by.full_name
        }
    )
    # Send to WebSocket group
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer
    channel_layer = get_channel_layer()
    group_name = f"notifications_{invitee.id}"
    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            'type': 'new_notification',
            'notification': {
                'id': str(notification.id),
                'notification_type': notification.notification_type,
                'title': notification.title,
                'message': notification.message,
                'sender': {
                    'id': notification.sender.id if notification.sender else None,
                    'full_name': notification.sender.full_name if notification.sender else None,
                    'email': notification.sender.email if notification.sender else None,
                } if notification.sender else None,
                'is_read': notification.is_read,
                'read_at': notification.read_at.isoformat() if notification.read_at else None,
                'created_at': notification.created_at.isoformat(),
                'extra_data': notification.extra_data or {}
            }
        }
    )
    return notification
