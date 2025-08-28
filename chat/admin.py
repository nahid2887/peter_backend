from django.contrib import admin
from .models import (
    Conversation, Message, MessageReadReceipt, UserStatus, Notification, 
    NotificationSettings, GroupMembership, DefaultGroup, DefaultGroupMembership
)


class GroupMembershipInline(admin.TabularInline):
    model = GroupMembership
    extra = 1
    fields = ['user', 'role', 'is_active', 'joined_at', 'added_by']
    readonly_fields = ['joined_at']
    raw_id_fields = ['user', 'added_by']


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'is_group', 'created_by', 'created_at', 'participant_count']
    list_filter = ['is_group', 'created_at']
    search_fields = ['name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    filter_horizontal = ['participants']
    raw_id_fields = ['created_by']
    
    def participant_count(self, obj):
        return obj.participants.count()
    participant_count.short_description = 'Participants'


@admin.register(GroupMembership)
class GroupMembershipAdmin(admin.ModelAdmin):
    list_display = ['conversation', 'user', 'role', 'is_active', 'joined_at', 'added_by']
    list_filter = ['role', 'is_active', 'joined_at']
    search_fields = ['user__full_name', 'user__email', 'conversation__name']
    readonly_fields = ['joined_at', 'left_at']
    raw_id_fields = ['conversation', 'user', 'added_by']


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['id', 'conversation', 'sender', 'content_preview', 'message_type', 'timestamp', 'is_edited']
    list_filter = ['message_type', 'timestamp', 'is_edited']
    search_fields = ['content', 'sender__full_name', 'sender__email']
    readonly_fields = ['id', 'timestamp', 'edited_at']
    raw_id_fields = ['conversation', 'sender', 'reply_to']
    
    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Content'


@admin.register(MessageReadReceipt)
class MessageReadReceiptAdmin(admin.ModelAdmin):
    list_display = ['message', 'user', 'read_at']
    list_filter = ['read_at']
    search_fields = ['user__full_name', 'user__email']
    readonly_fields = ['read_at']
    raw_id_fields = ['message', 'user']


@admin.register(UserStatus)
class UserStatusAdmin(admin.ModelAdmin):
    list_display = ['user', 'status', 'last_seen', 'last_activity', 'is_online']
    list_filter = ['status', 'last_seen']
    search_fields = ['user__full_name', 'user__email']
    readonly_fields = ['last_seen', 'last_activity']
    
    def is_online(self, obj):
        return obj.is_online()
    is_online.boolean = True
    is_online.short_description = 'Online'


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'recipient', 'sender', 'notification_type', 'is_read', 'created_at']
    list_filter = ['notification_type', 'is_read', 'created_at', 'is_sent']
    search_fields = ['title', 'message', 'recipient__full_name', 'recipient__email', 'sender__full_name']
    readonly_fields = ['id', 'created_at', 'read_at']
    raw_id_fields = ['recipient', 'sender', 'conversation', 'related_message']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'title', 'message', 'notification_type')
        }),
        ('Users', {
            'fields': ('recipient', 'sender')
        }),
        ('Related Objects', {
            'fields': ('conversation', 'related_message'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_read', 'is_sent', 'read_at')
        }),
        ('Metadata', {
            'fields': ('extra_data', 'created_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('recipient', 'sender', 'conversation')


@admin.register(NotificationSettings)
class NotificationSettingsAdmin(admin.ModelAdmin):
    list_display = ['user', 'enable_message_notifications', 'enable_mention_notifications', 'enable_group_notifications', 'enable_push_notifications']
    list_filter = ['enable_message_notifications', 'enable_mention_notifications', 'enable_group_notifications', 'enable_push_notifications', 'enable_email_notifications', 'do_not_disturb']
    search_fields = ['user__full_name', 'user__email']
    raw_id_fields = ['user']
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Message Notification Types', {
            'fields': ('enable_message_notifications', 'enable_mention_notifications', 'enable_group_notifications')
        }),
        ('Real-time Delivery Settings', {
            'fields': ('enable_push_notifications', 'enable_sound_notifications', 'enable_desktop_notifications'),
            'classes': ('collapse',)
        }),
        ('Email Notifications', {
            'fields': ('enable_email_notifications', 'email_notification_frequency'),
            'classes': ('collapse',)
        }),
        ('Do Not Disturb', {
            'fields': ('do_not_disturb', 'do_not_disturb_start', 'do_not_disturb_end'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
            'description': 'Read-only timestamp fields'
        })
    )
    
    readonly_fields = ['created_at', 'updated_at']


class DefaultGroupMembershipInline(admin.TabularInline):
    model = DefaultGroupMembership
    extra = 0
    fields = ['user', 'is_active', 'joined_at', 'left_at']
    readonly_fields = ['joined_at', 'left_at']
    raw_id_fields = ['user']


@admin.register(DefaultGroup)
class DefaultGroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'description', 'is_active', 'member_count', 'conversation_id', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at', 'conversation']
    inlines = [DefaultGroupMembershipInline]
    
    def member_count(self, obj):
        return obj.get_member_count()
    member_count.short_description = 'Active Members'
    
    def conversation_id(self, obj):
        return str(obj.conversation.id) if obj.conversation else 'Not Created'
    conversation_id.short_description = 'Conversation ID'


@admin.register(DefaultGroupMembership)
class DefaultGroupMembershipAdmin(admin.ModelAdmin):
    list_display = ['default_group', 'user', 'is_active', 'joined_at', 'left_at']
    list_filter = ['is_active', 'joined_at', 'default_group']
    search_fields = ['user__full_name', 'user__email', 'default_group__name']
    readonly_fields = ['joined_at', 'left_at']
    raw_id_fields = ['default_group', 'user']
