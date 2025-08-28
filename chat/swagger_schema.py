from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

# Common response schemas
error_response = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        'error': openapi.Schema(type=openapi.TYPE_STRING, description='Error message'),
    }
)

success_response = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        'success': openapi.Schema(type=openapi.TYPE_BOOLEAN, description='Operation success'),
        'message': openapi.Schema(type=openapi.TYPE_STRING, description='Success message'),
    }
)

# User search schema
user_search_response = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        'results': openapi.Schema(
            type=openapi.TYPE_ARRAY,
            items=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'id': openapi.Schema(type=openapi.TYPE_INTEGER, description='User ID'),
                    'email': openapi.Schema(type=openapi.TYPE_STRING, description='User email'),
                    'full_name': openapi.Schema(type=openapi.TYPE_STRING, description='User full name'),
                    'profile_photo_url': openapi.Schema(type=openapi.TYPE_STRING, description='Profile photo URL'),
                    'is_online': openapi.Schema(type=openapi.TYPE_BOOLEAN, description='Online status'),
                }
            )
        ),
        'count': openapi.Schema(type=openapi.TYPE_INTEGER, description='Number of results'),
    }
)

# Conversation schemas
conversation_list_response = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        'conversations': openapi.Schema(
            type=openapi.TYPE_ARRAY,
            items=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'id': openapi.Schema(type=openapi.TYPE_STRING, description='Conversation UUID'),
                    'name': openapi.Schema(type=openapi.TYPE_STRING, description='Conversation name'),
                    'is_group': openapi.Schema(type=openapi.TYPE_BOOLEAN, description='Is group chat'),
                    'display_name': openapi.Schema(type=openapi.TYPE_STRING, description='Display name'),
                    'unread_count': openapi.Schema(type=openapi.TYPE_INTEGER, description='Unread messages count'),
                    'created_at': openapi.Schema(type=openapi.TYPE_STRING, format='date-time'),
                    'updated_at': openapi.Schema(type=openapi.TYPE_STRING, format='date-time'),
                }
            )
        ),
        'count': openapi.Schema(type=openapi.TYPE_INTEGER, description='Number of conversations'),
    }
)

create_conversation_request = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    required=['participant_ids'],
    properties={
        'participant_ids': openapi.Schema(
            type=openapi.TYPE_ARRAY,
            items=openapi.Schema(type=openapi.TYPE_INTEGER),
            description='List of user IDs to include'
        ),
        'is_group': openapi.Schema(type=openapi.TYPE_BOOLEAN, default=False, description='Is group chat'),
        'name': openapi.Schema(type=openapi.TYPE_STRING, description='Group chat name (required for groups)'),
    }
)

# Message schemas
send_message_request = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    required=['content'],
    properties={
        'content': openapi.Schema(type=openapi.TYPE_STRING, description='Message content'),
        'message_type': openapi.Schema(type=openapi.TYPE_STRING, default='text', enum=['text', 'image', 'file'], description='Message type'),
        'reply_to': openapi.Schema(type=openapi.TYPE_STRING, description='UUID of message being replied to'),
    }
)

message_response = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        'message': openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'id': openapi.Schema(type=openapi.TYPE_STRING, description='Message UUID'),
                'content': openapi.Schema(type=openapi.TYPE_STRING, description='Message content'),
                'message_type': openapi.Schema(type=openapi.TYPE_STRING, description='Message type'),
                'timestamp': openapi.Schema(type=openapi.TYPE_STRING, format='date-time'),
                'is_edited': openapi.Schema(type=openapi.TYPE_BOOLEAN, description='Was message edited'),
                'sender': openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'full_name': openapi.Schema(type=openapi.TYPE_STRING),
                        'email': openapi.Schema(type=openapi.TYPE_STRING),
                    }
                ),
            }
        ),
        'success': openapi.Schema(type=openapi.TYPE_BOOLEAN),
    }
)

# Notification schemas
notification_response = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        'notifications': openapi.Schema(
            type=openapi.TYPE_ARRAY,
            items=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'id': openapi.Schema(type=openapi.TYPE_STRING, description='Notification UUID'),
                    'notification_type': openapi.Schema(type=openapi.TYPE_STRING, description='Notification type'),
                    'title': openapi.Schema(type=openapi.TYPE_STRING, description='Notification title'),
                    'message': openapi.Schema(type=openapi.TYPE_STRING, description='Notification message'),
                    'is_read': openapi.Schema(type=openapi.TYPE_BOOLEAN, description='Read status'),
                    'created_at': openapi.Schema(type=openapi.TYPE_STRING, format='date-time'),
                    'time_ago': openapi.Schema(type=openapi.TYPE_STRING, description='Human readable time'),
                    'sender': openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'full_name': openapi.Schema(type=openapi.TYPE_STRING),
                        }
                    ),
                }
            )
        ),
        'unread_count': openapi.Schema(type=openapi.TYPE_INTEGER, description='Total unread notifications'),
    }
)

unread_count_response = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        'unread_count': openapi.Schema(type=openapi.TYPE_INTEGER, description='Number of unread notifications'),
    }
)

# User status schemas
update_status_request = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    required=['status'],
    properties={
        'status': openapi.Schema(
            type=openapi.TYPE_STRING,
            enum=['online', 'away', 'offline'],
            description='User status'
        ),
    }
)

status_response = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        'status': openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'user': openapi.Schema(type=openapi.TYPE_OBJECT),
                'status': openapi.Schema(type=openapi.TYPE_STRING),
                'last_seen': openapi.Schema(type=openapi.TYPE_STRING, format='date-time'),
                'is_online': openapi.Schema(type=openapi.TYPE_BOOLEAN),
            }
        ),
        'message': openapi.Schema(type=openapi.TYPE_STRING),
    }
)

# Edit message schema
edit_message_request = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    required=['content'],
    properties={
        'content': openapi.Schema(type=openapi.TYPE_STRING, description='New message content'),
    }
)
