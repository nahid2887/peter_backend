from django.urls import path
from . import views, group_views, default_group_views
from .views import get_user_groups

app_name = 'chat'

urlpatterns = [
    # User search endpoints
    path('search-users/', views.search_users, name='search_users'),
    path('list-users/', views.list_users, name='list_users'),
    
    # Conversation endpoints
    path('conversations/', views.get_conversations, name='get_conversations'),
    path('conversations/create/', views.create_conversation, name='create_conversation'),
    path('conversations/<uuid:conversation_id>/', views.get_conversation_detail, name='get_conversation_detail'),
    path('conversations/<uuid:conversation_id>/delete/', views.delete_conversation, name='delete_conversation'),
    path('conversations/<uuid:conversation_id>/read/', views.mark_conversation_as_read, name='mark_conversation_as_read'),
    
    # Group management endpoints (using conversation system)
    path('conversations/create-group/', group_views.create_group, name='create_group'),
    path('conversations/<uuid:conversation_id>/add-members/', group_views.add_group_members, name='add_group_members'),
    path('conversations/<uuid:conversation_id>/remove-member/', group_views.remove_group_member, name='remove_group_member'),
    path('conversations/<uuid:conversation_id>/leave/', group_views.leave_group, name='leave_group'),
    path('conversations/<uuid:conversation_id>/change-name/', group_views.change_group_name, name='change_group_name'),
    path('conversations/<uuid:conversation_id>/promote-admin/', group_views.promote_to_admin, name='promote_to_admin'),
    path('conversations/<uuid:conversation_id>/members/', group_views.get_group_members, name='get_group_members'),
    path('conversations/<uuid:conversation_id>/delete-group/', group_views.delete_group, name='delete_group'),
    path('groups/user-groups/', get_user_groups, name='get_user_groups'),

    # Default Groups endpoints
    path('default-groups/', default_group_views.get_default_groups, name='get_default_groups'),
    path('default-groups/join/', default_group_views.join_default_groups, name='join_default_groups'),
    path('default-groups/leave/', default_group_views.leave_default_groups, name='leave_default_groups'),
    path('default-groups/my-groups/', default_group_views.get_user_default_groups, name='get_user_default_groups'),
    path('default-groups/<int:group_id>/members/', default_group_views.get_default_group_members, name='get_default_group_members'),

    # Message endpointss
    path('messages/<uuid:conversation_id>/send/', views.send_message, name='send_message'),
    path('messages/<uuid:message_id>/read/', views.mark_message_as_read, name='mark_message_as_read'),
    path('messages/<uuid:message_id>/delete/', views.delete_message, name='delete_message'),
    path('messages/<uuid:message_id>/edit/', views.edit_message, name='edit_message'),
    
    # User status endpoints
    path('status/update/', views.update_user_status, name='update_user_status'),
    path('status/<int:user_id>/', views.get_user_status, name='get_user_status'),
    
    # Notification endpoints
    path('notifications/', views.get_notifications, name='get_notifications'),
    path('notifications/<uuid:notification_id>/read/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/unread-count/', views.get_unread_count, name='get_unread_count'),
]
