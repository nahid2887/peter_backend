from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import Notification, NotificationSettings

User = get_user_model()


class SimpleNotificationService:
    """
    Simple notification service - creates notification when user gets message
    """
    
    @staticmethod
    def create_message_notification(message):
        """
        Create notifications for all participants when they receive a message
        """
        # Get recipients based on conversation type
        if message.conversation.is_group:
            # For group chats, get all active group members except the sender
            from .models import GroupMembership
            recipients = User.objects.filter(
                group_memberships__conversation=message.conversation,
                group_memberships__is_active=True
            ).exclude(id=message.sender.id).distinct()
        else:
            # For individual chats, get regular participants except the sender
            recipients = message.conversation.participants.exclude(id=message.sender.id)
        
        notifications = []
        
        for recipient in recipients:
            # Create simple notification
            if message.conversation.is_group:
                title = f"New message in {message.conversation.name or 'Group Chat'}"
            else:
                title = f"New message from {message.sender.full_name}"
            
            notification_text = message.content[:100]  # First 100 characters
            
            if len(message.content) > 100:
                notification_text += "..."
            
            notification = Notification.objects.create(
                recipient=recipient,
                sender=message.sender,
                notification_type='message',
                title=title,
                message=notification_text,
                conversation=message.conversation,
                related_message=message
            )
            
            notifications.append(notification)
        
        return notifications
    
    @staticmethod
    def get_user_notifications(user, limit=20):
        """
        Get recent notifications for a user
        """
        return user.notifications.all()[:limit]
    
    @staticmethod
    def get_unread_count(user):
        """
        Get count of unread notifications
        """
        return user.notifications.filter(is_read=False).count()
    
    @staticmethod
    def mark_as_read(notification_id, user):
        """
        Mark notification as read
        """
        try:
            notification = user.notifications.get(id=notification_id)
            notification.mark_as_read()
            return True
        except Notification.DoesNotExist:
            return False


# Create global instance
simple_notification_service = SimpleNotificationService()
