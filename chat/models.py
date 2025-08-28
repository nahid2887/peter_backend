from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid

User = get_user_model()


class Conversation(models.Model):
    """
    Represents a conversation between users (can be one-on-one or group chat)
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, blank=True, null=True)  # For group chats
    is_group = models.BooleanField(default=False)
    participants = models.ManyToManyField(User, related_name='conversations')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_conversations')
    
    class Meta:
        ordering = ['-updated_at']
    
    def __str__(self):
        if self.is_group and self.name:
            return self.name
        elif self.is_group:
            participants = list(self.participants.all()[:3])
            names = [p.full_name for p in participants]
            if len(names) > 2:
                return f"{', '.join(names[:2])} and {len(names)-2} others"
            return ', '.join(names)
        else:
            # For one-on-one chats, return the other participant's name
            participants = list(self.participants.all())
            if len(participants) == 2:
                return f"Chat between {participants[0].full_name} and {participants[1].full_name}"
            return "Chat"
    
    def get_last_message(self):
        """Get the last message in this conversation"""
        return self.messages.first()
    
    def get_last_activity_time(self):
        """Get the time of the last activity (message or creation)"""
        last_message = self.get_last_message()
        if last_message:
            return max(last_message.timestamp, self.created_at)
        return self.created_at
    
    def get_unread_count_for_user(self, user):
        """Get unread message count for a specific user"""
        return self.messages.filter(
            read_by__isnull=True
        ).exclude(sender=user).count()
    
    def get_active_participants(self):
        """Get active participants (for groups, only active members; for direct messages, all participants)"""
        if self.is_group:
            # For groups, check GroupMembership for active members
            return User.objects.filter(
                group_memberships__conversation=self,
                group_memberships__is_active=True
            )
        else:
            # For direct messages, return all participants
            return self.participants.all()
    
    def get_admins(self):
        """Get group admins"""
        if not self.is_group:
            return User.objects.none()
        
        return User.objects.filter(
            group_memberships__conversation=self,
            group_memberships__role='admin',
            group_memberships__is_active=True
        )
    
    def add_participant(self, user, added_by=None, role='member'):
        """Add a participant to the conversation"""
        if not self.is_group:
            # For direct messages, just add to participants
            self.participants.add(user)
            return None
        
        # For groups, manage through GroupMembership
        membership, created = GroupMembership.objects.get_or_create(
            conversation=self,
            user=user,
            defaults={
                'role': role,
                'added_by': added_by,
                'is_active': True
            }
        )
        
        if not created and not membership.is_active:
            # Reactivate if user was previously in the group
            membership.is_active = True
            membership.joined_at = timezone.now()
            membership.added_by = added_by
            membership.left_at = None
            membership.save()
        
        # Also add to the regular participants for backward compatibility
        self.participants.add(user)
        
        # Create system message
        Message.objects.create(
            conversation=self,
            sender=added_by or user,
            content=f"{user.full_name} joined the group" if added_by != user else f"{user.full_name} was added to the group",
            message_type='system'
        )
        
        return membership
    
    def remove_participant(self, user, removed_by=None):
        """Remove a participant from the conversation"""
        if not self.is_group:
            # For direct messages, just remove from participants
            self.participants.remove(user)
            return True
        
        # For groups, manage through GroupMembership or DefaultGroupMembership
        removed = False
        
        # Try to remove from regular GroupMembership first
        try:
            membership = GroupMembership.objects.get(
                conversation=self,
                user=user,
                is_active=True
            )
            membership.is_active = False
            membership.left_at = timezone.now()
            membership.save()
            removed = True
        except GroupMembership.DoesNotExist:
            pass
        
        # Also check for DefaultGroupMembership
        if not removed:
            try:
                default_membership = DefaultGroupMembership.objects.get(
                    default_group__conversation=self,
                    user=user,
                    is_active=True
                )
                default_membership.is_active = False
                default_membership.left_at = timezone.now()
                default_membership.save()
                removed = True
            except DefaultGroupMembership.DoesNotExist:
                pass
        
        # Always remove from regular participants list for consistency
        if user in self.participants.all():
            self.participants.remove(user)
            removed = True
        
        # Create system message if user was actually removed
        if removed:
            Message.objects.create(
                conversation=self,
                sender=removed_by or user,
                content=f"{user.full_name} was removed from the group" if removed_by and removed_by != user else f"{user.full_name} left the group",
                message_type='system'
            )
        
        return removed
    
    def change_group_name(self, new_name, changed_by):
        """Change the group name"""
        if not self.is_group:
            raise ValueError("Can only change name for group conversations")
        
        old_name = self.name
        self.name = new_name
        self.save()
        
        # Create system message
        Message.objects.create(
            conversation=self,
            sender=changed_by,
            content=f"{changed_by.full_name} changed the group name from '{old_name}' to '{new_name}'",
            message_type='system'
        )
    
    def promote_to_admin(self, user, promoted_by):
        """Promote a member to admin"""
        if not self.is_group:
            raise ValueError("Can only promote members in group conversations")
        
        try:
            membership = GroupMembership.objects.get(
                conversation=self,
                user=user,
                is_active=True
            )
            membership.role = 'admin'
            membership.save()
            
            # Create system message
            Message.objects.create(
                conversation=self,
                sender=promoted_by,
                content=f"{user.full_name} is now an admin",
                message_type='system'
            )
            
            return True
        except GroupMembership.DoesNotExist:
            return False


class GroupMembership(models.Model):
    """
    Represents membership in a group conversation with roles and permissions
    """
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('member', 'Member'),
    ]
    
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='group_memberships')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='member')
    joined_at = models.DateTimeField(auto_now_add=True)
    added_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='added_members')
    is_active = models.BooleanField(default=True)  # False when user leaves the group
    left_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ['conversation', 'user']
        indexes = [
            models.Index(fields=['conversation', 'is_active']),
            models.Index(fields=['user', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.user.full_name} - {self.get_role_display()} in {self.conversation.name or 'Group'}"
    
    def is_admin(self):
        """Check if user is admin of the group"""
        return self.role == 'admin' and self.is_active
    
    def can_add_members(self):
        """Check if user can add members to the group"""
        return self.is_admin()
    
    def can_remove_members(self):
        """Check if user can remove members from the group"""
        return self.is_admin()
    
    def can_change_group_name(self):
        """Check if user can change group name"""
        return self.is_admin()
    
    def leave_group(self):
        """Leave the group"""
        self.is_active = False
        self.left_at = timezone.now()
        self.save()
        
        # Also remove from regular participants to ensure they don't appear anywhere
        self.conversation.participants.remove(self.user)
        
        # Create a system message about leaving
        Message.objects.create(
            conversation=self.conversation,
            sender=self.user,
            content=f"{self.user.full_name} left the group",
            message_type='system'
        )


class Message(models.Model):
    """
    Represents a message in a conversation
    """
    MESSAGE_TYPES = [
        ('text', 'Text'),
        ('image', 'Image'),
        ('file', 'File'),
        ('system', 'System'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    content = models.TextField()
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPES, default='text')
    file_attachment = models.FileField(upload_to='chat_files/', blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(blank=True, null=True)
    is_edited = models.BooleanField(default=False)
    reply_to = models.ForeignKey('self', on_delete=models.SET_NULL, blank=True, null=True, related_name='replies')
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.sender.full_name}: {self.content[:50]}..."
    
    def mark_as_read_by(self, user):
        """Mark this message as read by a user"""
        read_receipt, created = MessageReadReceipt.objects.get_or_create(
            message=self,
            user=user,
            defaults={'read_at': timezone.now()}
        )
        return read_receipt


class MessageReadReceipt(models.Model):
    """
    Tracks which users have read which messages
    """
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='read_by')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='read_messages')
    read_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['message', 'user']
    
    def __str__(self):
        return f"{self.user.full_name} read message at {self.read_at}"


class UserStatus(models.Model):
    """
    Tracks user online status and last seen
    """
    STATUS_CHOICES = [
        ('online', 'Online'),
        ('away', 'Away'),
        ('offline', 'Offline'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='status')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='offline')
    last_seen = models.DateTimeField(auto_now=True)
    last_activity = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.full_name} - {self.status}"
    
    def is_online(self):
        """Check if user is currently online (active within last 5 minutes)"""
        return (timezone.now() - self.last_activity).seconds < 300


class Notification(models.Model):
    """
    Notification system for chat messages and other events
    """
    NOTIFICATION_TYPES = [
        ('message', 'New Message'),
        ('mention', 'Mentioned in Message'),
        ('group_add', 'Added to Group'),
        ('group_remove', 'Removed from Group'),
        ('typing', 'User Typing'),
        ('call', 'Call Notification'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_notifications', null=True, blank=True)
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default='message')
    title = models.CharField(max_length=255)
    message = models.TextField()
    
    # Related objects
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, null=True, blank=True)
    related_message = models.ForeignKey(Message, on_delete=models.CASCADE, null=True, blank=True)
    
    # Notification status
    is_read = models.BooleanField(default=False)
    is_sent = models.BooleanField(default=False)  # For push notifications
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Metadata
    extra_data = models.JSONField(default=dict, blank=True)  # For additional notification data
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.recipient.full_name}"
    
    def mark_as_read(self):
        """Mark notification as read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])


class DefaultGroup(models.Model):
    """
    Represents default groups that users can join (like Kindergarten, 1st Grade, etc.)
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Auto-create conversation when first user joins
    conversation = models.OneToOneField(
        Conversation, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name='default_group'
    )
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def get_or_create_conversation(self):
        """Get or create conversation for this default group"""
        if not self.conversation:
            # Create conversation for this default group
            self.conversation = Conversation.objects.create(
                name=self.name,
                is_group=True,
                created_by=None  # System created
            )
            self.save()
        return self.conversation
    
    def get_member_count(self):
        """Get current member count"""
        if not self.conversation:
            return 0
        return self.conversation.get_active_participants().count()
    
    def add_user(self, user):
        """Add user to this default group"""
        conversation = self.get_or_create_conversation()
        membership = conversation.add_participant(user, role='member')
        
        # Create default group membership record
        DefaultGroupMembership.objects.get_or_create(
            default_group=self,
            user=user,
            defaults={'is_active': True}
        )
        
        return membership
    
    def remove_user(self, user):
        """Remove user from this default group"""
        if self.conversation:
            success = self.conversation.remove_participant(user)
            if success:
                # Update default group membership
                try:
                    membership = DefaultGroupMembership.objects.get(
                        default_group=self,
                        user=user
                    )
                    membership.is_active = False
                    membership.left_at = timezone.now()
                    membership.save()
                except DefaultGroupMembership.DoesNotExist:
                    pass
            return success
        return False


class DefaultGroupMembership(models.Model):
    """
    Tracks user membership in default groups
    """
    default_group = models.ForeignKey(
        DefaultGroup, 
        on_delete=models.CASCADE, 
        related_name='memberships'
    )
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='default_group_memberships'
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ['default_group', 'user']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['default_group', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.user.full_name} - {self.default_group.name}"
    
    def leave(self):
        """Leave the default group"""
        self.is_active = False
        self.left_at = timezone.now()
        self.save()
        
        # Also remove from the conversation
        if self.default_group.conversation:
            self.default_group.conversation.remove_participant(self.user)


class NotificationSettings(models.Model):
    """
    User preferences for notifications
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='notification_settings')
    
    # Message notifications
    enable_message_notifications = models.BooleanField(default=True)
    enable_mention_notifications = models.BooleanField(default=True)
    enable_group_notifications = models.BooleanField(default=True)
    
    # Real-time notifications
    enable_push_notifications = models.BooleanField(default=True)
    enable_sound_notifications = models.BooleanField(default=True)
    enable_desktop_notifications = models.BooleanField(default=True)
    
    # Email notifications
    enable_email_notifications = models.BooleanField(default=False)
    email_notification_frequency = models.CharField(
        max_length=20,
        choices=[
            ('immediate', 'Immediate'),
            ('hourly', 'Hourly'),
            ('daily', 'Daily'),
            ('never', 'Never'),
        ],
        default='never'
    )
    
    # Do not disturb
    do_not_disturb = models.BooleanField(default=False)
    do_not_disturb_start = models.TimeField(null=True, blank=True)  # e.g., 22:00
    do_not_disturb_end = models.TimeField(null=True, blank=True)    # e.g., 08:00
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Notification settings for {self.user.full_name}"
    
    def is_do_not_disturb_active(self):
        """Check if do not disturb is currently active"""
        if not self.do_not_disturb or not self.do_not_disturb_start or not self.do_not_disturb_end:
            return False
        
        from datetime import datetime, time
        current_time = datetime.now().time()
        
        # Handle overnight DND (e.g., 22:00 to 08:00)
        if self.do_not_disturb_start > self.do_not_disturb_end:
            return current_time >= self.do_not_disturb_start or current_time <= self.do_not_disturb_end
        else:
            return self.do_not_disturb_start <= current_time <= self.do_not_disturb_end
