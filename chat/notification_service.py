from django.contrib.auth import get_user_model
from django.utils import timezone
import json

from .models import Notification, NotificationSettings, Conversation, Message

User = get_user_model()


class NotificationService:
    """Service class for handling all notification logic"""
    
    def __init__(self):
        pass
    
    def create_message_notification(self, message, exclude_sender=True):
        """
        Create notifications for new messages
        """
        conversation = message.conversation
        recipients = conversation.participants.all()
        
        if exclude_sender:
            recipients = recipients.exclude(id=message.sender.id)
        
        notifications_created = []
        
        for recipient in recipients:
            # Check if user wants message notifications
            settings = self.get_user_notification_settings(recipient)
            
            if not settings.enable_message_notifications:
                continue
            
            # Check do not disturb
            if settings.is_do_not_disturb_active():
                continue
            
            # Check if user is online (don't notify if they're actively chatting)
            if self.is_user_online_in_conversation(recipient, conversation):
                continue
            
            # Create notification
            notification = self.create_notification(
                recipient=recipient,
                sender=message.sender,
                notification_type='message',
                title=f"New message from {message.sender.full_name}",
                message=self.truncate_message(message.content),
                conversation=conversation,
                related_message=message,
                extra_data={
                    'message_type': message.message_type,
                    'conversation_type': 'group' if conversation.is_group else 'direct'
                }
            )
            
            notifications_created.append(notification)
            
            # Send push notification if enabled
            if settings.enable_push_notifications:
                self.send_push_notification(notification)
        
        return notifications_created
    
    def create_mention_notification(self, message, mentioned_users):
        """
        Create notifications for mentioned users in messages
        """
        notifications_created = []
        
        for user in mentioned_users:
            if user == message.sender:
                continue  # Don't notify the sender
            
            settings = self.get_user_notification_settings(user)
            
            if not settings.enable_mention_notifications:
                continue
            
            if settings.is_do_not_disturb_active():
                continue
            
            notification = self.create_notification(
                recipient=user,
                sender=message.sender,
                notification_type='mention',
                title=f"{message.sender.full_name} mentioned you",
                message=self.truncate_message(message.content),
                conversation=message.conversation,
                related_message=message,
                extra_data={'mention_context': message.content}
            )
            
            notifications_created.append(notification)
            
            # Send push notification
            if settings.enable_push_notifications:
                self.send_push_notification(notification)
        
        return notifications_created
    
    def create_group_notification(self, conversation, action, actor, affected_users, message=None):
        """
        Create notifications for group actions (add/remove users)
        """
        notifications_created = []
        
        for user in affected_users:
            if user == actor:
                continue
            
            settings = self.get_user_notification_settings(user)
            
            if not settings.enable_group_notifications:
                continue
            
            if action == 'add':
                title = f"{actor.full_name} added you to {conversation.name or 'a group'}"
                notification_type = 'group_add'
            elif action == 'remove':
                title = f"{actor.full_name} removed you from {conversation.name or 'a group'}"
                notification_type = 'group_remove'
            else:
                continue
            
            notification = self.create_notification(
                recipient=user,
                sender=actor,
                notification_type=notification_type,
                title=title,
                message=message or f"Group: {conversation.name or 'Unnamed Group'}",
                conversation=conversation,
                extra_data={'action': action, 'group_name': conversation.name}
            )
            
            notifications_created.append(notification)
            
            # Send push notification
            if settings.enable_push_notifications:
                self.send_push_notification(notification)
        
        return notifications_created
    
    def create_notification(self, recipient, notification_type, title, message, **kwargs):
        """
        Create a notification in the database
        """
        notification = Notification.objects.create(
            recipient=recipient,
            notification_type=notification_type,
            title=title,
            message=message,
            **kwargs
        )
        return notification
    
    def send_push_notification(self, notification):
        """
        Send push notification (placeholder for actual push service)
        This would integrate with services like Firebase, OneSignal, etc.
        """
        # Placeholder for push notification service
        # In a real implementation, you would integrate with:
        # - Firebase Cloud Messaging (FCM)
        # - Apple Push Notification Service (APNS)
        # - Web Push API
        # - OneSignal, Pusher, etc.
        
        push_data = {
            'title': notification.title,
            'body': notification.message,
            'user_id': notification.recipient.id,
            'notification_id': str(notification.id),
            'type': notification.notification_type
        }
        
        print(f"Push notification sent to {notification.recipient.full_name}: {push_data}")
        # TODO: Implement actual push notification sending
    
    def get_user_notification_settings(self, user):
        """
        Get or create notification settings for a user
        """
        settings, created = NotificationSettings.objects.get_or_create(
            user=user,
            defaults={
                'enable_message_notifications': True,
                'enable_mention_notifications': True,
                'enable_group_notifications': True,
                'enable_push_notifications': True,
            }
        )
        return settings
    
    def is_user_online_in_conversation(self, user, conversation):
        """
        Check if user is currently online and active in the conversation
        This helps avoid spamming notifications when user is actively chatting
        """
        try:
            user_status = user.status
            if not user_status.is_online():
                return False
            
            # Additional logic could check if user has the conversation open
            # This would require frontend to send "conversation_focus" events
            return False  # For now, always send notifications
            
        except:
            return False
    
    def truncate_message(self, content, max_length=100):
        """
        Truncate message content for notifications
        """
        if len(content) <= max_length:
            return content
        return content[:max_length-3] + '...'
    
    def mark_conversation_notifications_as_read(self, user, conversation):
        """
        Mark all notifications for a conversation as read when user opens it
        """
        notifications = Notification.objects.filter(
            recipient=user,
            conversation=conversation,
            is_read=False
        )
        
        for notification in notifications:
            notification.mark_as_read()
        
        # Send real-time update about read notifications
        # Note: WebSocket functionality removed
    
    def get_unread_count(self, user):
        """
        Get total unread notification count for a user
        """
        return Notification.objects.filter(
            recipient=user,
            is_read=False
        ).count()


# Global instance
notification_service = NotificationService()
