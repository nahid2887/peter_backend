
from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.contrib.auth import get_user_model
from django.db.models import Q, Prefetch, Max, Count
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.db import transaction

from .models import Conversation, Message, MessageReadReceipt, UserStatus, Notification, NotificationSettings, GroupMembership
from .serializers import (
    UserSearchSerializer, ConversationListSerializer, ConversationDetailSerializer,
    CreateConversationSerializer, MessageSerializer, SendMessageSerializer,
    UserStatusSerializer, NotificationSerializer, NotificationSettingsSerializer
)
from .simple_notification_service import simple_notification_service
from .swagger_schema import *

User = get_user_model()


class MessagePagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 100


@swagger_auto_schema(
    method='get',
    operation_description="Search for users by name or email (like Facebook Messenger)",
    manual_parameters=[
        openapi.Parameter(
            'q', 
            openapi.IN_QUERY, 
            description="Search query (name or email)", 
            type=openapi.TYPE_STRING,
            required=True
        ),
    ],
    responses={
        200: user_search_response,
        400: error_response,
    },
    tags=['User Search']
)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def search_users(request):
    """
    Search for users by name or email (like Facebook Messenger)
    """
    query = request.GET.get('q', '').strip()
    
    if not query:
        return Response({
            'results': [],
            'message': 'Please provide a search query'
        })
    
    if len(query) < 2:
        return Response({
            'results': [],
            'message': 'Search query must be at least 2 characters'
        })
    
    # Search by full name or email
    users = User.objects.filter(
        Q(full_name__icontains=query) | Q(email__icontains=query)
    ).exclude(
        id=request.user.id  # Exclude current user from search results
    ).select_related('status').order_by('full_name')[:20]  # Limit to 20 results
    
    serializer = UserSearchSerializer(users, many=True, context={'request': request})
    
    return Response({
        'results': serializer.data,
        'count': len(serializer.data)
    })


@swagger_auto_schema(
    method='get',
    operation_description="Get paginated list of all users for selection in groups/conversations",
    manual_parameters=[
        openapi.Parameter(
            'page', 
            openapi.IN_QUERY, 
            description="Page number", 
            type=openapi.TYPE_INTEGER
        ),
        openapi.Parameter(
            'page_size', 
            openapi.IN_QUERY, 
            description="Number of users per page (max 50)", 
            type=openapi.TYPE_INTEGER
        ),
        openapi.Parameter(
            'search', 
            openapi.IN_QUERY, 
            description="Optional search query to filter users", 
            type=openapi.TYPE_STRING
        ),
    ],
    responses={
        200: openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'results': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(type=openapi.TYPE_OBJECT)
                ),
                'count': openapi.Schema(type=openapi.TYPE_INTEGER),
                'next': openapi.Schema(type=openapi.TYPE_STRING),
                'previous': openapi.Schema(type=openapi.TYPE_STRING),
            }
        ),
    },
    tags=['User Search']
)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def list_users(request):
    """
    Get paginated list of all users for adding to conversations/groups
    """
    search_query = request.GET.get('search', '').strip()
    
    # Start with all users except current user
    users = User.objects.exclude(id=request.user.id).select_related('status')
    
    # Apply search filter if provided
    if search_query:
        users = users.filter(
            Q(full_name__icontains=search_query) | Q(email__icontains=search_query)
        )
    
    # Order by full name
    users = users.order_by('full_name')
    
    # Paginate the results
    class UserPagination(PageNumberPagination):
        page_size = 20
        page_size_query_param = 'page_size'
        max_page_size = 50
    
    paginator = UserPagination()
    paginated_users = paginator.paginate_queryset(users, request)
    
    serializer = UserSearchSerializer(
        paginated_users, 
        many=True, 
        context={'request': request}
    )
    
    return paginator.get_paginated_response(serializer.data)


@swagger_auto_schema(
    method='get',
    operation_description="Get all conversations for the current user with last message and unread count",
    responses={
        200: conversation_list_response,
    },
    tags=['Conversations']
)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_conversations(request):
    """
    Get all conversations for the current user (both individual chats and groups)
    Optimized to show conversations with recent activity first
    """
    from django.db.models import Case, When, Value
    from django.db.models.functions import Coalesce
    
    # Get conversations where user is a participant
    # For groups: also check if user is an active group member
    conversations = Conversation.objects.filter(
        Q(participants=request.user) |  # Regular participants
        Q(is_group=True, memberships__user=request.user, memberships__is_active=True)  # Active group members
    ).distinct().prefetch_related(
        'participants',
        'memberships__user'
    ).annotate(
        last_message_time=Max('messages__timestamp'),
        # Use the most recent of last_message_time or created_at for sorting
        last_activity=Coalesce('last_message_time', 'created_at')
    ).order_by('-last_activity')
    
    serializer = ConversationListSerializer(
        conversations, 
        many=True, 
        context={'request': request}
    )
    
    return Response({
        'conversations': serializer.data,
        'count': len(serializer.data)
    })


@swagger_auto_schema(
    method='get',
    operation_description="Get conversation details with paginated messages",
    manual_parameters=[
        openapi.Parameter(
            'page', 
            openapi.IN_QUERY, 
            description="Page number", 
            type=openapi.TYPE_INTEGER
        ),
        openapi.Parameter(
            'page_size', 
            openapi.IN_QUERY, 
            description="Number of messages per page (max 100)", 
            type=openapi.TYPE_INTEGER
        ),
    ],
    responses={
        200: openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'conversation': openapi.Schema(type=openapi.TYPE_OBJECT),
                'messages': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_OBJECT)),
                'count': openapi.Schema(type=openapi.TYPE_INTEGER),
                'next': openapi.Schema(type=openapi.TYPE_STRING),
                'previous': openapi.Schema(type=openapi.TYPE_STRING),
            }
        ),
        404: error_response,
    },
    tags=['Conversations']
)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_conversation_detail(request, conversation_id):
    """
    Get conversation details with messages (works for both individual chats and groups)
    """
    # Check if user has access to this conversation
    # For individual chats: check participants
    # For groups: check both participants and active group membership
    conversations = Conversation.objects.prefetch_related(
        'participants',
        'memberships__user',
        Prefetch(
            'messages',
            queryset=Message.objects.select_related('sender', 'reply_to__sender')
            .prefetch_related('read_by__user')
            .order_by('-timestamp')
        )
    ).filter(
        Q(participants=request.user) |  # Regular participants
        Q(is_group=True, memberships__user=request.user, memberships__is_active=True)  # Active group members
    ).filter(id=conversation_id).distinct()
    
    if not conversations.exists():
        from django.http import Http404
        raise Http404("Conversation not found")
    
    conversation = conversations.first()
    
    # Paginate messages
    paginator = MessagePagination()
    messages = conversation.messages.all()
    paginated_messages = paginator.paginate_queryset(messages, request)
    
    # Mark messages as read
    unread_messages = messages.exclude(sender=request.user).exclude(
        read_by__user=request.user
    )
    for message in unread_messages:
        message.mark_as_read_by(request.user)
    
    # Serialize conversation
    conversation_serializer = ConversationDetailSerializer(
        conversation, 
        context={'request': request}
    )
    
    # Serialize paginated messages
    message_serializer = MessageSerializer(
        paginated_messages, 
        many=True, 
        context={'request': request}
    )
    
    return paginator.get_paginated_response({
        'conversation': conversation_serializer.data,
        'messages': message_serializer.data
    })


@swagger_auto_schema(
    method='post',
    operation_description="Create a new conversation or get existing one-on-one conversation",
    request_body=create_conversation_request,
    responses={
        201: openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'conversation': openapi.Schema(type=openapi.TYPE_OBJECT),
                'created': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                'message': openapi.Schema(type=openapi.TYPE_STRING),
            }
        ),
        400: error_response,
    },
    tags=['Conversations']
)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def create_conversation(request):
    """
    Create a new one-to-one conversation or return existing one.
    A user can only have one active conversation at a time.
    
    If participant_ids is provided: creates conversation with those participants
    If no participant_ids provided: returns existing conversation or creates empty one
    """
    serializer = CreateConversationSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    participant_ids = serializer.validated_data.get('participant_ids', [])
    is_group = serializer.validated_data.get('is_group', False)
    name = serializer.validated_data.get('name', '')
    
    if is_group:
        # Redirect group creation to the proper endpoint
        return Response({
            'error': 'Use the /groups/create/ endpoint for creating group conversations'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    with transaction.atomic():
        # Global guard: If user already has an existing one-to-one conversation, always return it
        existing_user_conversation = Conversation.objects.filter(
            is_group=False,
            participants__id=request.user.id
        ).annotate(
            participant_count=Count('participants', distinct=True)
        ).filter(
            participant_count=2
        ).distinct().first()
        
        if existing_user_conversation:
            serializer_resp = ConversationDetailSerializer(
                existing_user_conversation,
                context={'request': request}
            )
            return Response({
                'conversation': serializer_resp.data,
                'created': False,
                'message': 'Existing conversation found. Only one conversation allowed at a time.',
                'conversation_id': str(existing_user_conversation.id)
            }, status=status.HTTP_200_OK)
        
        # Check if participants are provided
        if not participant_ids:
            # No participants provided, create empty conversation for current user only
            conversation = Conversation.objects.create(
                name=name if is_group else None,
                is_group=is_group,
                created_by=request.user
            )
            conversation.participants.set([request.user])
            message = 'Empty conversation created. Add a participant to start chatting.'
        else:
            # Participants provided - check if conversation already exists between these specific users
            if len(participant_ids) == 1:
                other_user_id = participant_ids[0]
                
                existing_conversation = Conversation.objects.filter(
                    is_group=False,
                    participants__id__in=[request.user.id, other_user_id]
                ).annotate(
                    participant_count=Count('participants', distinct=True)
                ).filter(
                    participant_count=2
                ).distinct().first()
                
                if existing_conversation:
                    serializer_resp = ConversationDetailSerializer(
                        existing_conversation,
                        context={'request': request}
                    )
                    return Response({
                        'conversation': serializer_resp.data,
                        'created': False,
                        'message': 'Conversation already exists between these users.',
                        'conversation_id': str(existing_conversation.id)
                    }, status=status.HTTP_200_OK)
            elif len(participant_ids) > 1:
                # Multiple participants - this should be a group conversation
                return Response({
                    'error': 'Multiple participants detected. Use the /groups/create/ endpoint for group conversations'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # No existing conversation between these specific users, create new one
            all_participant_ids = [request.user.id] + participant_ids
            
            conversation = Conversation.objects.create(
                name=name if is_group else None,
                is_group=is_group,
                created_by=request.user
            )
            
            # Add all participants
            participants = User.objects.filter(id__in=all_participant_ids)
            conversation.participants.set(participants)
            
            message = 'Conversation created successfully'
    
    serializer_resp = ConversationDetailSerializer(
        conversation,
        context={'request': request}
    )
    
    return Response({
        'conversation': serializer_resp.data,
        'created': True,
        'message': message,
        'conversation_id': str(conversation.id)
    }, status=status.HTTP_201_CREATED)


@swagger_auto_schema(
    method='delete',
    operation_description="Delete a conversation (only one-to-one conversations can be deleted by participants)",
    responses={
        200: openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'message': openapi.Schema(type=openapi.TYPE_STRING),
                'success': openapi.Schema(type=openapi.TYPE_BOOLEAN),
            }
        ),
        400: error_response,
        403: error_response,
        404: error_response,
    },
    tags=['Conversations']
)
@api_view(['DELETE'])
@permission_classes([permissions.IsAuthenticated])
def delete_conversation(request, conversation_id):
    """
    Delete a conversation. 
    - Only participants of one-to-one conversations can delete them
    - After deletion, users can create new conversations
    """
    try:
        # Get conversation that user is a participant of
        conversation = Conversation.objects.filter(
            Q(participants=request.user) |  # Regular participants
            Q(is_group=True, memberships__user=request.user, memberships__is_active=True)  # Active group members
        ).filter(id=conversation_id).distinct().first()
        
        if not conversation:
            return Response({
                'error': 'Conversation not found or you do not have permission to delete it'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Only allow deletion of one-to-one conversations
        if conversation.is_group:
            return Response({
                'error': 'Group conversations cannot be deleted. Use leave group instead.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if user is a participant in this one-to-one conversation
        if not conversation.participants.filter(id=request.user.id).exists():
            return Response({
                'error': 'You are not a participant in this conversation'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Delete the conversation (this will cascade delete messages due to foreign key)
        conversation_name = str(conversation)
        conversation.delete()
        
        return Response({
            'success': True,
            'message': f'Conversation "{conversation_name}" has been deleted successfully. You can now create a new conversation.'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'error': f'An error occurred while deleting the conversation: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@swagger_auto_schema(
    method='post',
    operation_description="Send a message to a conversation and automatically create notifications for recipients",
    request_body=send_message_request,
    responses={
        201: message_response,
        400: error_response,
        404: error_response,
    },
    tags=['Messages']
)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def send_message(request, conversation_id):
    """
    Send a message to a conversation (works for both individual chats and groups)
    """
    from .models import DefaultGroupMembership
    
    conversations = Conversation.objects.filter(
        Q(participants=request.user) |  # Regular participants
        Q(is_group=True, memberships__user=request.user, memberships__is_active=True) |  # Active group members
        Q(is_group=True, default_group__memberships__user=request.user, default_group__memberships__is_active=True)  # Active default group members
    ).filter(id=conversation_id).distinct()
    
    if not conversations.exists():
        from django.http import Http404
        raise Http404("Conversation not found")
    
    conversation = conversations.first()
    
    # Double-check user membership for security
    user_is_member = (
        conversation.participants.filter(id=request.user.id).exists() or
        (conversation.is_group and GroupMembership.objects.filter(
            conversation=conversation, user=request.user, is_active=True
        ).exists()) or
        (conversation.is_group and DefaultGroupMembership.objects.filter(
            default_group__conversation=conversation, user=request.user, is_active=True
        ).exists())
    )
    
    if not user_is_member:
        return Response({
            'success': False,
            'error': 'You are not a member of this conversation'
        }, status=status.HTTP_403_FORBIDDEN)
    
    serializer = SendMessageSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    # Create message
    message = Message.objects.create(
        conversation=conversation,
        sender=request.user,
        **serializer.validated_data
    )
    
    # Create notifications for recipients
    try:
        simple_notification_service.create_message_notification(message)
    except Exception as e:
        # Don't fail the message send if notification creation fails
        print(f"Error creating notifications: {e}")
    
    # Update conversation timestamp
    conversation.updated_at = timezone.now()
    conversation.save()
    
    # Serialize message for response
    message_serializer = MessageSerializer(
        message,
        context={'request': request}
    )
    
    return Response({
        'message': message_serializer.data,
        'success': True
    }, status=status.HTTP_201_CREATED)


@swagger_auto_schema(
    method='post',
    operation_description="Mark a specific message as read by the current user",
    responses={
        200: openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'message': openapi.Schema(type=openapi.TYPE_STRING),
                'read_at': openapi.Schema(type=openapi.TYPE_STRING, format='date-time'),
            }
        ),
        400: error_response,
        404: error_response,
    },
    tags=['Messages']
)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def mark_message_as_read(request, message_id):
    """
    Mark a specific message as read
    """
    message = get_object_or_404(
        Message.objects.filter(
            Q(conversation__participants=request.user) |  # Regular participants
            Q(conversation__is_group=True, conversation__memberships__user=request.user, conversation__memberships__is_active=True)  # Active group members
        ),
        id=message_id
    )
    
    # Don't mark own messages as read
    if message.sender == request.user:
        return Response({
            'message': 'Cannot mark your own message as read'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    read_receipt = message.mark_as_read_by(request.user)
    
    return Response({
        'message': 'Message marked as read',
        'read_at': read_receipt.read_at
    })


@swagger_auto_schema(
    method='post',
    operation_description="Mark all messages in a conversation as read by the current user",
    responses={
        200: openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'message': openapi.Schema(type=openapi.TYPE_STRING),
                'marked_count': openapi.Schema(type=openapi.TYPE_INTEGER),
            }
        ),
        404: error_response,
    },
    tags=['Messages']
)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def mark_conversation_as_read(request, conversation_id):
    """
    Mark all messages in a conversation as read
    """
    conversations = Conversation.objects.filter(
        Q(participants=request.user) |  # Regular participants
        Q(is_group=True, memberships__user=request.user, memberships__is_active=True)  # Active group members
    ).filter(id=conversation_id).distinct()
    
    if not conversations.exists():
        from django.http import Http404
        raise Http404("Conversation not found")
    
    conversation = conversations.first()
    
    # Get all unread messages from other users
    unread_messages = conversation.messages.exclude(
        sender=request.user
    ).exclude(
        read_by__user=request.user
    )
    
    # Mark them as read
    for message in unread_messages:
        message.mark_as_read_by(request.user)
    
    return Response({
        'message': f'Marked {unread_messages.count()} messages as read',
        'marked_count': unread_messages.count()
    })


@swagger_auto_schema(
    method='post',
    operation_description="Update user's online status (online, away, offline)",
    request_body=update_status_request,
    responses={
        200: status_response,
        400: error_response,
    },
    tags=['User Status']
)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def update_user_status(request):
    """
    Update user's online status
    """
    status_value = request.data.get('status', 'online')
    
    if status_value not in ['online', 'away', 'offline']:
        return Response({
            'error': 'Invalid status. Must be one of: online, away, offline'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    user_status, created = UserStatus.objects.get_or_create(
        user=request.user,
        defaults={'status': status_value}
    )
    
    if not created:
        user_status.status = status_value
        user_status.last_activity = timezone.now()
        user_status.save()
    
    serializer = UserStatusSerializer(user_status, context={'request': request})
    
    return Response({
        'status': serializer.data,
        'message': f'Status updated to {status_value}'
    })


@swagger_auto_schema(
    method='get',
    operation_description="Get a user's online status and last seen information",
    responses={
        200: openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'user': openapi.Schema(type=openapi.TYPE_OBJECT),
                'status': openapi.Schema(type=openapi.TYPE_STRING),
                'last_seen': openapi.Schema(type=openapi.TYPE_STRING, format='date-time'),
                'is_online': openapi.Schema(type=openapi.TYPE_BOOLEAN),
            }
        ),
        404: error_response,
    },
    tags=['User Status']
)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_user_status(request, user_id):
    """
    Get a user's online status
    """
    user = get_object_or_404(User, id=user_id)
    
    try:
        user_status = user.status
        serializer = UserStatusSerializer(user_status, context={'request': request})
        return Response(serializer.data)
    except UserStatus.DoesNotExist:
        return Response({
            'user': UserSearchSerializer(user, context={'request': request}).data,
            'status': 'offline',
            'last_seen': None,
            'is_online': False
        })


@swagger_auto_schema(
    method='delete',
    operation_description="Delete a message (only the sender can delete their own messages)",
    responses={
        200: openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'message': openapi.Schema(type=openapi.TYPE_STRING),
            }
        ),
        404: error_response,
    },
    tags=['Messages']
)
@api_view(['DELETE'])
@permission_classes([permissions.IsAuthenticated])
def delete_message(request, message_id):
    """
    Delete a message (only sender can delete)
    """
    message = get_object_or_404(
        Message,
        id=message_id,
        sender=request.user
    )
    
    # Store conversation for updating timestamp
    conversation = message.conversation
    
    # Delete the message
    message.delete()
    
    # Update conversation timestamp to last remaining message
    last_message = conversation.messages.first()
    if last_message:
        conversation.updated_at = last_message.timestamp
        conversation.save()
    
    return Response({
        'message': 'Message deleted successfully'
    })


@swagger_auto_schema(
    method='put',
    operation_description="Edit a message (only the sender can edit their own messages)",
    request_body=edit_message_request,
    responses={
        200: openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'message': openapi.Schema(type=openapi.TYPE_OBJECT),
                'success': openapi.Schema(type=openapi.TYPE_BOOLEAN),
            }
        ),
        400: error_response,
        404: error_response,
    },
    tags=['Messages']
)
@api_view(['PUT'])
@permission_classes([permissions.IsAuthenticated])
def edit_message(request, message_id):
    """
    Edit a message (only sender can edit)
    """
    message = get_object_or_404(
        Message,
        id=message_id,
        sender=request.user
    )
    
    new_content = request.data.get('content', '').strip()
    
    if not new_content:
        return Response({
            'error': 'Message content cannot be empty'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Update message
    message.content = new_content
    message.is_edited = True
    message.edited_at = timezone.now()
    message.save()
    
    # Serialize and return updated message
    serializer = MessageSerializer(message, context={'request': request})
    
    return Response({
        'message': serializer.data,
        'success': True
    })


# Notification Management Views

@swagger_auto_schema(
    method='get',
    operation_description="Get user's notifications with optional limit parameter",
    manual_parameters=[
        openapi.Parameter(
            'limit', 
            openapi.IN_QUERY, 
            description="Maximum number of notifications to return (default: 20)", 
            type=openapi.TYPE_INTEGER
        ),
    ],
    responses={
        200: notification_response,
    },
    tags=['Notifications']
)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_notifications(request):
    """
    Get user's notifications
    """
    limit = int(request.GET.get('limit', 20))
    notifications = simple_notification_service.get_user_notifications(request.user, limit)
    
    serializer = NotificationSerializer(notifications, many=True)
    
    return Response({
        'notifications': serializer.data,
        'unread_count': simple_notification_service.get_unread_count(request.user)
    })


@swagger_auto_schema(
    method='post',
    operation_description="Mark a specific notification as read",
    responses={
        200: success_response,
        404: error_response,
    },
    tags=['Notifications']
)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def mark_notification_read(request, notification_id):
    """
    Mark a notification as read
    """
    success = simple_notification_service.mark_as_read(notification_id, request.user)
    
    if success:
        # Broadcast updated unread count via WebSocket
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            
            channel_layer = get_channel_layer()
            notification_group_name = f'notifications_{request.user.id}'
            
            # Get updated unread count
            unread_count = simple_notification_service.get_unread_count(request.user)
            
            # Send to WebSocket
            async_to_sync(channel_layer.group_send)(
                notification_group_name,
                {
                    'type': 'unread_count_update',
                    'count': unread_count
                }
            )
        except Exception as e:
            # Don't fail the request if WebSocket broadcast fails
            print(f"Error broadcasting unread count: {e}")
        
        return Response({
            'success': True,
            'message': 'Notification marked as read'
        })
    else:
        return Response({
            'error': 'Notification not found'
        }, status=status.HTTP_404_NOT_FOUND)


@swagger_auto_schema(
    method='get',
    operation_description="Get count of unread notifications for the current user",
    responses={
        200: unread_count_response,
    },
    tags=['Notifications']
)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_unread_count(request):
    """
    Get count of unread notifications
    """
    count = simple_notification_service.get_unread_count(request.user)
    
    return Response({
        'unread_count': count
    })



@swagger_auto_schema(
    method='get',
    operation_description="Get a list of group conversations where the user is an admin (admin-only groups)",
    responses={
        200: openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'groups': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'id': openapi.Schema(type=openapi.TYPE_STRING, description='Group ID'),
                            'name': openapi.Schema(type=openapi.TYPE_STRING, description='Group name'),
                        
                        }
                    )
                ),
                'count': openapi.Schema(type=openapi.TYPE_INTEGER, description='Number of groups'),
            }
        ),
        404: error_response,
    },
    tags=['Groups']
)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_user_groups(request):
    """
    Get a list of group conversations where the user is an admin (admin-only groups)
    """
    groups = Conversation.objects.filter(
        is_group=True,
        memberships__user=request.user,
        memberships__is_active=True
    ).prefetch_related('memberships__user').distinct()

    group_list = []
    for group in groups:
        membership = group.memberships.filter(user=request.user).first()
        is_admin = getattr(membership, 'is_admin', False) if membership else False
        name = group.name if isinstance(group.name, str) or group.name is None else ''
        group_list.append({
            'id': str(group.id),
            'name': name if name is not None else '',
            
            
        })

    return Response({
        'groups': group_list,
        'count': len(group_list)
    })