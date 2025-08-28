from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db.models import Q, Max
from .models import Conversation, Message, MessageReadReceipt, UserStatus, Notification, NotificationSettings, GroupMembership, DefaultGroup, DefaultGroupMembership

User = get_user_model()


class UserSearchSerializer(serializers.ModelSerializer):
    """Serializer for user search results"""
    profile_photo_url = serializers.SerializerMethodField()
    is_online = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'email', 'full_name', 'profile_photo_url', 'is_online']
    
    def get_profile_photo_url(self, obj):
        if hasattr(obj, 'profile_photo') and obj.profile_photo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.profile_photo.url)
            return obj.profile_photo.url
        return None
    
    def get_is_online(self, obj):
        try:
            return obj.status.is_online()
        except UserStatus.DoesNotExist:
            return False


class GroupMembershipSerializer(serializers.ModelSerializer):
    """Serializer for group membership"""
    user = UserSearchSerializer(read_only=True)
    added_by = UserSearchSerializer(read_only=True)
    
    class Meta:
        model = GroupMembership
        fields = [
            'user', 'role', 'joined_at', 'added_by', 'is_active', 
            'left_at'
        ]
        read_only_fields = ['joined_at', 'left_at']


class GroupParticipantSerializer(serializers.ModelSerializer):
    """Serializer for group participants with their roles"""
    profile_photo_url = serializers.SerializerMethodField()
    is_online = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()
    can_remove = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'email', 'full_name', 'profile_photo_url', 'is_online', 'role', 'can_remove']
    
    def get_profile_photo_url(self, obj):
        if obj.profile_photo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.profile_photo.url)
        return None
    
    def get_is_online(self, obj):
        try:
            return obj.status.is_online()
        except UserStatus.DoesNotExist:
            return False
    
    def get_role(self, obj):
        conversation = self.context.get('conversation')
        if conversation and conversation.is_group:
            try:
                membership = GroupMembership.objects.get(
                    conversation=conversation,
                    user=obj,
                    is_active=True
                )
                return membership.get_role_display()
            except GroupMembership.DoesNotExist:
                pass
        return None
    
    def get_can_remove(self, obj):
        conversation = self.context.get('conversation')
        current_user = self.context.get('current_user')
        
        if not conversation or not conversation.is_group or not current_user:
            return False
        
        # Creator can remove anyone except themselves
        if conversation.created_by == current_user and obj != current_user:
            return True
        
        # Admins can remove members (but not other admins or themselves)
        try:
            current_membership = GroupMembership.objects.get(
                conversation=conversation,
                user=current_user,
                is_active=True
            )
            target_membership = GroupMembership.objects.get(
                conversation=conversation,
                user=obj,
                is_active=True
            )
            
            if current_membership.is_admin() and target_membership.role == 'member':
                return True
                
        except GroupMembership.DoesNotExist:
            pass
        
        return False



class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for notifications"""
    sender = serializers.SerializerMethodField()
    conversation_name = serializers.SerializerMethodField()
    time_ago = serializers.SerializerMethodField()
    
    class Meta:
        model = Notification
        fields = [
            'id', 'notification_type', 'title', 'message', 'sender',
            'conversation', 'conversation_name', 'related_message',
            'is_read', 'read_at', 'created_at', 'time_ago', 'extra_data'
        ]
        read_only_fields = ['id', 'created_at', 'time_ago']
    
    def get_sender(self, obj):
        return UserSearchSerializer(obj.sender, context=self.context).data if obj.sender else None

    def get_conversation_name(self, obj):
        if obj.conversation:
            if obj.conversation.is_group:
                return obj.conversation.name or "Group Chat"
            else:
                # For one-on-one chats, return the other participant's name
                request = self.context.get('request')
                if request and request.user:
                    other_participants = obj.conversation.participants.exclude(id=request.user.id)
                    if other_participants.exists():
                        return other_participants.first().full_name
                return "Chat"
        return None
    
    def get_time_ago(self, obj):
        from django.utils.timesince import timesince
        return timesince(obj.created_at)


class NotificationSettingsSerializer(serializers.ModelSerializer):
    """Serializer for notification settings"""
    
    class Meta:
        model = NotificationSettings
        fields = [
            'enable_message_notifications', 'enable_mention_notifications',
            'enable_group_notifications', 'enable_push_notifications',
            'enable_sound_notifications', 'enable_desktop_notifications',
            'enable_email_notifications', 'email_notification_frequency',
            'do_not_disturb', 'do_not_disturb_start', 'do_not_disturb_end'
        ]


class UserStatusSerializer(serializers.ModelSerializer):
    """Serializer for user status"""
    user = UserSearchSerializer(read_only=True)
    
    class Meta:
        model = UserStatus
        fields = ['user', 'status', 'last_seen', 'is_online']


class MessageReadReceiptSerializer(serializers.ModelSerializer):
    """Serializer for message read receipts"""
    user = serializers.SerializerMethodField()
    
    class Meta:
        model = MessageReadReceipt
        fields = ['user', 'read_at']

    def get_user(self, obj):
        return UserSearchSerializer(obj.user, context=self.context).data


class MessageSerializer(serializers.ModelSerializer):
    """Serializer for messages"""
    sender = serializers.SerializerMethodField()
    sender_profile_photo_url = serializers.SerializerMethodField()
    read_by = MessageReadReceiptSerializer(many=True, read_only=True)
    reply_to_message = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Message
        fields = [
            'id', 'conversation', 'sender', 'sender_profile_photo_url', 'content', 'message_type',
            'file_attachment', 'file_url', 'timestamp', 'edited_at',
            'is_edited', 'reply_to', 'reply_to_message', 'read_by'
        ]
        read_only_fields = ['id', 'sender', 'timestamp', 'edited_at', 'is_edited']

    def get_sender(self, obj):
        # Defensive: always include profile_photo_url, even if sender is None or missing photo
        sender = obj.sender
        if sender is None:
            return {
                'id': None,
                'full_name': None,
                'email': None,
                'profile_photo_url': None,
                'is_online': None,
            }
        sender_data = UserSearchSerializer(sender, context=self.context).data
        return {
            'id': sender_data.get('id'),
            'full_name': sender_data.get('full_name'),
            'email': sender_data.get('email'),
            'profile_photo_url': sender_data.get('profile_photo_url'),
            'is_online': sender_data.get('is_online'),
        }

    def get_sender_profile_photo_url(self, obj):
        sender = obj.sender
        if sender and hasattr(sender, 'profile_photo') and sender.profile_photo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(sender.profile_photo.url)
            return sender.profile_photo.url
        return None
    
    def get_reply_to_message(self, obj):
        if obj.reply_to:
            return {
                'id': obj.reply_to.id,
                'sender': obj.reply_to.sender.full_name,
                'content': obj.reply_to.content[:100] + '...' if len(obj.reply_to.content) > 100 else obj.reply_to.content,
                'message_type': obj.reply_to.message_type
            }
        return None
    
    def get_file_url(self, obj):
        if obj.file_attachment:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file_attachment.url)
        return None


class ConversationListSerializer(serializers.ModelSerializer):
    """Serializer for conversation list view"""
    participants = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    display_name = serializers.SerializerMethodField()
    display_photo = serializers.SerializerMethodField()
    participant_count = serializers.SerializerMethodField()
    user_role = serializers.SerializerMethodField()
    
    class Meta:
        model = Conversation
        fields = [
            'id', 'name', 'is_group', 'participants', 'created_at',
            'updated_at', 'last_message', 'unread_count',
            'display_name', 'display_photo', 'participant_count', 'user_role'
        ]
    
    def get_participants(self, obj):
        if obj.is_group:
            # For groups, get active participants with their roles
            active_participants = obj.get_active_participants()[:5]  # Limit to 5 for list view
            return GroupParticipantSerializer(
                active_participants, 
                many=True, 
                context={
                    'request': self.context.get('request'),
                    'conversation': obj,
                    'current_user': self.context.get('request').user if self.context.get('request') else None
                }
            ).data
        else:
            # For direct messages, return the other participant
            request = self.context.get('request')
            if request and request.user.is_authenticated:
                other_participants = obj.participants.exclude(id=request.user.id)
                return UserSearchSerializer(
                    other_participants, 
                    many=True, 
                    context={'request': request}
                ).data
        return []
    
    def get_participant_count(self, obj):
        if obj.is_group:
            return obj.get_active_participants().count()
        return obj.participants.count()
    
    def get_user_role(self, obj):
        request = self.context.get('request')
        if obj.is_group and request and request.user.is_authenticated:
            try:
                membership = GroupMembership.objects.get(
                    conversation=obj,
                    user=request.user,
                    is_active=True
                )
                return membership.get_role_display()
            except GroupMembership.DoesNotExist:
                return None
        return None
    
    def get_last_message(self, obj):
        # Get the most recent message
        last_message = obj.messages.select_related('sender').order_by('-timestamp').first()
        if last_message:
            return {
                'id': last_message.id,
                'sender': last_message.sender.full_name,
                'content': last_message.content[:100] + '...' if len(last_message.content) > 100 else last_message.content,
                'timestamp': last_message.timestamp,
                'message_type': last_message.message_type
            }
        return None
    
    def get_unread_count(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.get_unread_count_for_user(request.user)
        return 0
    
    def get_display_name(self, obj):
        request = self.context.get('request')
        if obj.is_group:
            return obj.name or "Group Chat"
        else:
            # For one-on-one chats, show the other participant's name
            if request and request.user.is_authenticated:
                other_participants = obj.participants.exclude(id=request.user.id)
                if other_participants.exists():
                    return other_participants.first().full_name
            return "Chat"
    
    def get_display_photo(self, obj):
        request = self.context.get('request')
        if obj.is_group:
            return None  # Groups don't have profile photos for now
        else:
            # For one-on-one chats, show the other participant's photo
            if request and request.user.is_authenticated:
                other_participants = obj.participants.exclude(id=request.user.id)
                if other_participants.exists():
                    other_user = other_participants.first()
                    if other_user.profile_photo:
                        return request.build_absolute_uri(other_user.profile_photo.url)
            return None


class ConversationDetailSerializer(serializers.ModelSerializer):
    """Serializer for conversation detail view"""
    participants = serializers.SerializerMethodField()
    messages = MessageSerializer(many=True, read_only=True)
    
    class Meta:
        model = Conversation
        fields = [
            'id', 'name', 'is_group', 'participants', 'created_at',
            'updated_at', 'messages'
        ]
    
    def get_participants(self, obj):
        if obj.is_group:
            # For groups, get only active participants
            active_participants = obj.get_active_participants()
            return GroupParticipantSerializer(
                active_participants,
                many=True,
                context={
                    'request': self.context.get('request'),
                    'conversation': obj,
                    'current_user': self.context.get('request').user if self.context.get('request') else None
                }
            ).data
        else:
            # For direct messages, return all participants
            return UserSearchSerializer(
                obj.participants.all(),
                many=True,
                context={'request': self.context.get('request')}
            ).data


class ConversationSerializer(serializers.ModelSerializer):
    """Basic conversation serializer"""
    participants = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    display_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Conversation
        fields = [
            'id', 'name', 'is_group', 'participants', 'created_at',
            'updated_at', 'last_message', 'unread_count', 'display_name'
        ]
    
    def get_participants(self, obj):
        if obj.is_group:
            # For groups, get only active participants
            active_participants = obj.get_active_participants()
            return UserSearchSerializer(
                active_participants,
                many=True,
                context={'request': self.context.get('request')}
            ).data
        else:
            # For direct messages, return all participants
            return UserSearchSerializer(
                obj.participants.all(),
                many=True,
                context={'request': self.context.get('request')}
            ).data
    
    def get_last_message(self, obj):
        last_message = obj.get_last_message()
        if last_message:
            return {
                'id': last_message.id,
                'sender': last_message.sender.full_name,
                'content': last_message.content[:50] + '...' if len(last_message.content) > 50 else last_message.content,
                'timestamp': last_message.timestamp,
                'message_type': last_message.message_type
            }
        return None
    
    def get_unread_count(self, obj):
        user = self.context.get('user')
        if user:
            return obj.get_unread_count_for_user(user)
        return 0
    
    def get_display_name(self, obj):
        user = self.context.get('user')
        if obj.is_group:
            return obj.name or "Group Chat"
        else:
            # For one-on-one chats, show the other participant's name
            if user:
                other_participants = obj.participants.exclude(id=user.id)
                if other_participants.exists():
                    return other_participants.first().full_name
            return "Chat"


class CreateConversationSerializer(serializers.Serializer):
    """Serializer for creating new conversations"""
    participant_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True,
        help_text="List of user IDs to include in the conversation (optional - if empty, returns existing conversation or creates empty one)"
    )
    is_group = serializers.BooleanField(default=False)
    name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    
    def validate_participant_ids(self, value):
        """Validate that all participant IDs exist"""
        if value:  # Only validate if participant_ids is provided
            users = User.objects.filter(id__in=value)
            if users.count() != len(value):
                raise serializers.ValidationError("Some user IDs are invalid")
        return value
    
    def validate(self, data):
        """Additional validation"""
        if data.get('is_group') and not data.get('name'):
            raise serializers.ValidationError("Group conversations must have a name")
        
        participant_ids = data.get('participant_ids', [])
        if not data.get('is_group') and len(participant_ids) > 1:
            raise serializers.ValidationError("One-on-one conversations can only have one other participant")
        
        return data


class SendMessageSerializer(serializers.ModelSerializer):
    """Serializer for sending messages"""
    
    class Meta:
        model = Message
        fields = ['content', 'message_type', 'file_attachment', 'reply_to']
    
    def validate(self, data):
        """Validate message data"""
        if data.get('message_type') == 'text' and not data.get('content'):
            raise serializers.ValidationError("Text messages must have content")
        
        if data.get('message_type') == 'file' and not data.get('file_attachment'):
            raise serializers.ValidationError("File messages must have a file attachment")
        
        return data


class CreateGroupSerializer(serializers.Serializer):
    """Serializer for creating group conversations"""
    name = serializers.CharField(max_length=255, help_text="Group name")
    participant_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
        help_text="List of user IDs to include in the group"
    )
    
    def validate_participant_ids(self, value):
        """Validate that all participant IDs exist"""
        users = User.objects.filter(id__in=value)
        if users.count() != len(value):
            invalid_ids = set(value) - set(users.values_list('id', flat=True))
            raise serializers.ValidationError(f"Invalid user IDs: {list(invalid_ids)}")
        return value
    
    def validate_name(self, value):
        """Validate group name"""
        if not value.strip():
            raise serializers.ValidationError("Group name cannot be empty")
        return value.strip()


class AddGroupMemberSerializer(serializers.Serializer):
    """Serializer for adding members to a group"""
    user_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
        help_text="List of user IDs to add to the group"
    )
    
    def validate_user_ids(self, value):
        """Validate that all user IDs exist"""
        users = User.objects.filter(id__in=value)
        if users.count() != len(value):
            invalid_ids = set(value) - set(users.values_list('id', flat=True))
            raise serializers.ValidationError(f"Invalid user IDs: {list(invalid_ids)}")
        return value


class RemoveGroupMemberSerializer(serializers.Serializer):
    """Serializer for removing a member from a group"""
    user_id = serializers.IntegerField(help_text="User ID to remove from the group")
    
    def validate_user_id(self, value):
        """Validate that user ID exists"""
        try:
            User.objects.get(id=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid user ID")
        return value


class ChangeGroupNameSerializer(serializers.Serializer):
    """Serializer for changing group name"""
    name = serializers.CharField(max_length=255, help_text="New group name")
    
    def validate_name(self, value):
        """Validate group name"""
        if not value.strip():
            raise serializers.ValidationError("Group name cannot be empty")
        return value.strip()


class PromoteToAdminSerializer(serializers.Serializer):
    """Serializer for promoting a member to admin"""
    user_id = serializers.IntegerField(help_text="User ID to promote to admin")
    
    def validate_user_id(self, value):
        """Validate that user ID exists"""
        try:
            User.objects.get(id=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid user ID")
        return value


class DefaultGroupSerializer(serializers.ModelSerializer):
    """Serializer for default groups"""
    member_count = serializers.SerializerMethodField()
    is_member = serializers.SerializerMethodField()
    conversation_id = serializers.SerializerMethodField()
    
    class Meta:
        model = DefaultGroup
        fields = [
            'id', 'name', 'description', 'is_active', 
            'member_count', 'is_member', 'conversation_id',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_member_count(self, obj):
        return obj.get_member_count()
    
    def get_is_member(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return DefaultGroupMembership.objects.filter(
                default_group=obj,
                user=request.user,
                is_active=True
            ).exists()
        return False
    
    def get_conversation_id(self, obj):
        return str(obj.conversation.id) if obj.conversation else None


class DefaultGroupMembershipSerializer(serializers.ModelSerializer):
    """Serializer for default group membership"""
    user = UserSearchSerializer(read_only=True)
    default_group = DefaultGroupSerializer(read_only=True)
    
    class Meta:
        model = DefaultGroupMembership
        fields = [
            'id', 'user', 'default_group', 'joined_at', 
            'left_at', 'is_active'
        ]
        read_only_fields = ['id', 'joined_at', 'left_at']


class DefaultGroupCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating default groups (admin only)"""
    
    class Meta:
        model = DefaultGroup
        fields = ['name', 'description']
    
    def validate_name(self, value):
        """Ensure group name is unique"""
        if DefaultGroup.objects.filter(name__iexact=value).exists():
            raise serializers.ValidationError("A group with this name already exists")
        return value
