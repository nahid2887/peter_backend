# from django.urls import path
# from . import views

# app_name = 'chat'

# urlpatterns = [
#     # User search endpoints
#     path('search-users/', views.search_users, name='search_users'),
    
#     # Conversation endpoints
#     path('conversations/', views.get_conversations, name='get_conversations'),
#     path('conversations/create/', views.create_conversation, name='create_conversation'),
#     path('conversations/<uuid:conversation_id>/', views.get_conversation_detail, name='get_conversation_detail'),
#     path('conversations/<uuid:conversation_id>/read/', views.mark_conversation_as_read, name='mark_conversation_as_read'),
    
#     # Message endpoints
#     path('conversations/<uuid:conversation_id>/send/', views.send_message, name='send_message'),
#     path('messages/<uuid:message_id>/read/', views.mark_message_as_read, name='mark_message_as_read'),
#     path('messages/<uuid:message_id>/delete/', views.delete_message, name='delete_message'),
#     path('messages/<uuid:message_id>/edit/', views.edit_message, name='edit_message'),
    
#     # User status endpoints
#     path('status/update/', views.update_user_status, name='update_user_status'),
#     path('status/<int:user_id>/', views.get_user_status, name='get_user_status'),
# ]
