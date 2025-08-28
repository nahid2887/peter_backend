import json
import uuid
import traceback
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from .models import Conversation, Message
from .jwt_auth_middleware import JWTAuthMiddleware
from django.core.exceptions import ObjectDoesNotExist

User = get_user_model()


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.conversation_group_name = f'chat_{self.conversation_id}'
        
        # Get user from middleware (already authenticated)
        self.user = self.scope.get('user')
        if not self.user or self.user.is_anonymous:
            await self.close()
            return
        
        # Check if user is participant in this conversation
        is_participant = await self.check_user_participation()
        if not is_participant:
            await self.close()
            return
        
        # Join conversation group
        await self.channel_layer.group_add(
            self.conversation_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Load and send all conversations to the client
        await self.send_all_conversations()
        
        # Load and send all messages for this conversation
        await self.send_conversation_messages()
        
        # Mark messages as read for this user
        await self.mark_messages_as_read()

    async def disconnect(self, close_code):
        # Leave conversation group
        if hasattr(self, 'conversation_group_name'):
            await self.channel_layer.group_discard(
                self.conversation_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type', 'message')
            
            if message_type == 'message':
                content = text_data_json['content']
                
                # Check if user is still an active participant before allowing message sending
                is_participant = await self.check_user_participation()
                if not is_participant:
                    await self.send(text_data=json.dumps({
                        'type': 'error',
                        'message': 'You are no longer a member of this conversation.'
                    }))
                    # Close the connection since user is no longer a participant
                    await self.close()
                    return
                
                try:
                    # Save message to database
                    message = await self.save_message(content)
                    print(f"Saved message: {message.id}")
                    
                    # Create notifications for other participants and get broadcast data
                    try:
                        notification_data = await self.create_message_notifications(message)
                        print(f"Got notification data with {len(notification_data.get('recipients', []))} recipients")
                        
                        # Broadcast notifications asynchronously
                        try:
                            await self.broadcast_notifications(notification_data)
                            print("Broadcast completed")
                        except Exception as broadcast_error:
                            print(f"Error during broadcast (non-critical): {broadcast_error}")
                            # Don't fail message sending if broadcast fails
                    except Exception as notification_error:
                        print(f"Error creating notifications (non-critical): {notification_error}")
                        # Don't fail message sending if notification creation fails
                    
                    # Send message to conversation group
                    # Always use BASE_URL for profile_photo_url if available
                    profile_photo_url = None
                    if hasattr(message.sender, 'profile_photo') and message.sender.profile_photo:
                        from django.conf import settings
                        base_url = getattr(settings, 'BASE_URL', None)
                        if base_url:
                            profile_photo_url = base_url.rstrip('/') + message.sender.profile_photo.url
                        else:
                            profile_photo_url = message.sender.profile_photo.url
                    else:
                        profile_photo_url = None

                    await self.channel_layer.group_send(
                        self.conversation_group_name,
                        {
                            'type': 'chat_message',
                            'message': {
                                'id': str(message.id),
                                'content': message.content,
                                'sender': {
                                    'id': message.sender.id,
                                    'full_name': message.sender.full_name,
                                    'email': message.sender.email,
                                    'profile_photo_url': profile_photo_url,
                                },
                                'timestamp': message.timestamp.isoformat(),
                                'is_read': False
                            }
                        }
                    )
                    print(f"Message sent to conversation group: {self.conversation_group_name}")
                    
                except Exception as e:
                    print(f"Error in message handling: {e}")
                    import traceback
                    traceback.print_exc()
                    # Send error back to client
                    await self.send(text_data=json.dumps({
                        'type': 'error',
                        'error': f'Failed to process message: {str(e)}'
                    }))
                
            elif message_type == 'get_conversations':
                # Client requesting to refresh conversations list
                await self.send_all_conversations()
                
            elif message_type == 'get_messages':
                # Client requesting to refresh messages for this conversation
                await self.send_conversation_messages()
                
        except Exception as e:
            await self.send(text_data=json.dumps({
                'error': str(e)
            }))

    async def chat_message(self, event):
        # Check if user is still an active participant before delivering the message
        is_participant = await self.check_user_participation()
        if not is_participant:
            # User is no longer a participant, close the connection
            await self.close()
            return
        
        message = event['message']
        
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': message
        }))

    @database_sync_to_async
    def check_user_participation(self):
        try:
            from django.db.models import Q
            from .models import GroupMembership, DefaultGroupMembership
            
            conversation = Conversation.objects.get(id=self.conversation_id)
            
            # Check regular participants (for individual chats)
            is_regular_participant = conversation.participants.filter(id=self.user.id).exists()
            
            # For group chats, also check active group membership
            is_group_member = False
            if conversation.is_group:
                # Check regular group membership
                is_group_member = GroupMembership.objects.filter(
                    conversation=conversation,
                    user=self.user,
                    is_active=True
                ).exists()
                
                # Also check default group membership
                if not is_group_member:
                    is_group_member = DefaultGroupMembership.objects.filter(
                        default_group__conversation=conversation,
                        user=self.user,
                        is_active=True
                    ).exists()
            
            return is_regular_participant or is_group_member
            
        except ObjectDoesNotExist:
            return False

    async def send_all_conversations(self):
        """Load and send all user's conversations on WebSocket connect"""
        try:
            conversations_data = await self.get_user_conversations()
            
            await self.send(text_data=json.dumps({
                'type': 'conversations_list',
                'conversations': conversations_data
            }))
        except Exception as e:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'Failed to load conversations: {str(e)}'
            }))

    async def send_conversation_messages(self):
        """Load and send all messages for the current conversation"""
        try:
            messages_data = await self.get_conversation_messages()
            
            await self.send(text_data=json.dumps({
                'type': 'conversation_messages',
                'conversation_id': self.conversation_id,
                'messages': messages_data
            }))
        except Exception as e:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'Failed to load messages: {str(e)}'
            }))

    @database_sync_to_async
    def get_user_conversations(self):
        """Get all conversations for the current user with last message"""
        from django.db.models import Q
        
        try:
            # Get conversations where user is a participant - simplified version
            conversations_list = []
            conversations = Conversation.objects.filter(
                Q(participants=self.user) |  # Regular participants
                Q(is_group=True, memberships__user=self.user, memberships__is_active=True)  # Active group members
            ).distinct().prefetch_related('participants')[:20]  # Limit to 20 conversations
            
            for conv in conversations:
                try:
                    participants_names = []
                    if conv.is_group:
                        participants_names = [conv.name or "Group Chat"]
                    else:
                        other_participants = conv.participants.exclude(id=self.user.id)
                        participants_names = [p.full_name or p.email for p in other_participants]
                    
                    # Get last message - simplified
                    last_message = None
                    try:
                        last_msg = conv.messages.order_by('-timestamp').first()
                        if last_msg:
                            last_message = {
                                'content': last_msg.content[:100],  # Limit content length
                                'timestamp': last_msg.timestamp.isoformat(),
                                'sender_name': last_msg.sender.full_name or last_msg.sender.email
                            }
                    except:
                        last_message = None
                    
                    conversations_list.append({
                        'id': str(conv.id),
                        'name': conv.name or '',
                        'is_group': conv.is_group,
                        'participant_names': participants_names,
                        'last_message': last_message,
                        'created_at': conv.created_at.isoformat()
                    })
                except Exception as e:
                    # Skip this conversation if there's an error
                    continue
            
            return conversations_list
            
        except Exception as e:
            # Return empty list if there's a major error
            return []

    @database_sync_to_async
    def get_conversation_messages(self):
        """Get all messages for the current conversation"""
        try:
            conversation = Conversation.objects.get(id=self.conversation_id)
            
            # Get all messages for this conversation, ordered by timestamp
            messages = Message.objects.filter(
                conversation=conversation
            ).select_related('sender').order_by('timestamp')[:100]  # Limit to last 100 messages
            
            messages_list = []
            for message in messages:
                try:
                    # Check if message is read by current user - simplified
                    is_read_by_user = False
                    try:
                        is_read_by_user = message.read_by.filter(user=self.user).exists()
                    except:
                        pass
                    
                    # Always use BASE_URL for profile_photo_url if available
                    profile_photo_url = None
                    if hasattr(message.sender, 'profile_photo') and message.sender.profile_photo:
                        from django.conf import settings
                        base_url = getattr(settings, 'BASE_URL', None)
                        if base_url:
                            profile_photo_url = base_url.rstrip('/') + message.sender.profile_photo.url
                        else:
                            profile_photo_url = message.sender.profile_photo.url
                    else:
                        profile_photo_url = None

                    message_data = {
                        'id': str(message.id),
                        'content': message.content,
                        'sender': {
                            'id': message.sender.id,
                            'full_name': message.sender.full_name or message.sender.email,
                            'email': message.sender.email,
                            'profile_photo_url': profile_photo_url,
                        },
                        'timestamp': message.timestamp.isoformat(),
                        'is_read': is_read_by_user,
                        'is_own_message': message.sender.id == self.user.id
                    }
                    
                    # Add reply information if exists - simplified
                    try:
                        if hasattr(message, 'reply_to') and message.reply_to:
                            message_data['reply_to'] = {
                                'id': str(message.reply_to.id),
                                'content': message.reply_to.content[:50],  # Limit reply content
                                'sender_name': message.reply_to.sender.full_name or message.reply_to.sender.email
                            }
                    except:
                        pass
                    
                    messages_list.append(message_data)
                except Exception as e:
                    # Skip this message if there's an error
                    continue
            
            return messages_list
            
        except Exception as e:
            # Return empty list if there's an error
            return []

    @database_sync_to_async
    def mark_messages_as_read(self):
        """Mark all unread messages in this conversation as read by the current user"""
        try:
            from .models import MessageRead
            conversation = Conversation.objects.get(id=self.conversation_id)
            
            # Get unread messages (not sent by current user and not already read by them)
            unread_messages = Message.objects.filter(
                conversation=conversation
            ).exclude(sender=self.user).exclude(
                read_by__user=self.user
            )[:50]  # Limit to 50 messages
            
            # Mark them as read
            for message in unread_messages:
                try:
                    MessageRead.objects.get_or_create(
                        message=message,
                        user=self.user
                    )
                except:
                    # Skip if there's an error with this message
                    continue
            
            return True
        except Exception as e:
            return False

    @database_sync_to_async
    def save_message(self, content):
        conversation = Conversation.objects.get(id=self.conversation_id)
        message = Message.objects.create(
            conversation=conversation,
            sender=self.user,
            content=content
        )
        return message

    @database_sync_to_async
    def create_message_notifications(self, message):
        """Create notifications for message sent via WebSocket"""
        try:
            print(f"Creating notifications for message: {message.id}")
            
            # Try to import notification service - if it fails, continue without notifications
            try:
                from .simple_notification_service import simple_notification_service
                notifications = simple_notification_service.create_message_notification(message)
                print(f"Created {len(notifications) if notifications else 0} notifications")
            except ImportError as e:
                print(f"Could not import simple_notification_service: {e}")
                notifications = []
            except Exception as e:
                print(f"Error creating notifications: {e}")
                notifications = []
            
            # Get recipients based on conversation type
            conversation = message.conversation
            recipients = []
            
            if conversation.is_group:
                # For group chats, get all active group members except the sender
                try:
                    from .models import GroupMembership
                    recipients = list(User.objects.filter(
                        group_memberships__conversation=conversation,
                        group_memberships__is_active=True
                    ).exclude(id=message.sender.id).distinct())
                    print(f"Found {len(recipients)} group recipients")
                except Exception as e:
                    print(f"Error getting group recipients: {e}")
            else:
                # For individual chats, get regular participants except the sender
                try:
                    recipients = list(conversation.participants.exclude(id=message.sender.id))
                    print(f"Found {len(recipients)} individual chat recipients")
                except Exception as e:
                    print(f"Error getting individual chat recipients: {e}")
            
            # Return data needed for async broadcasting
            return {
                'notifications': notifications,
                'recipients': recipients,
                'conversation': conversation,
                'message': message
            }
            
        except Exception as e:
            print(f"Error in create_message_notifications: {e}")
            import traceback
            traceback.print_exc()
            return {
                'notifications': [],
                'recipients': [],
                'conversation': None,
                'message': None
            }

    async def broadcast_notifications(self, notification_data):
        """Broadcast notifications via WebSocket"""
        try:
            notifications = notification_data.get('notifications', [])
            recipients = notification_data.get('recipients', [])
            conversation = notification_data.get('conversation')
            message = notification_data.get('message')
            
            print(f"Broadcasting notifications: {len(recipients)} recipients")
            
            if not recipients or not message:
                print("No recipients or message, skipping broadcast")
                return
            
            # Process each recipient individually with error isolation
            for recipient in recipients:
                try:
                    notification_group_name = f'notifications_{recipient.id}'
                    print(f"Processing notifications for user {recipient.id}")
                    
                    # Get updated unread count - with error handling
                    try:
                        unread_count = await self.get_unread_count_for_user(recipient)
                        print(f"Got unread count {unread_count} for user {recipient.id}")
                    except Exception as e:
                        print(f"Error getting unread count for user {recipient.id}: {e}")
                        unread_count = 0
                    
                    # Send unread count update - with individual error handling
                    try:
                        await self.channel_layer.group_send(
                            notification_group_name,
                            {
                                'type': 'unread_count_update',
                                'count': unread_count
                            }
                        )
                        print(f"Sent unread count to user {recipient.id}")
                    except Exception as e:
                        print(f"Error sending unread count to user {recipient.id}: {e}")
                        continue
                    
                    # Send the new notification - with error handling
                    if notifications and len(notifications) > 0:
                        try:
                            # Build full absolute profile_photo_url for sender
                            profile_photo_url = None
                            if hasattr(message.sender, 'profile_photo') and message.sender.profile_photo:
                                try:
                                    request = self.scope.get('request')
                                except Exception:
                                    request = None
                                if request:
                                    profile_photo_url = request.build_absolute_uri(message.sender.profile_photo.url)
                                else:
                                    from django.conf import settings
                                    base_url = getattr(settings, 'BASE_URL', None)
                                    if base_url:
                                        profile_photo_url = base_url.rstrip('/') + message.sender.profile_photo.url
                                    else:
                                        profile_photo_url = message.sender.profile_photo.url
                            notification_data_payload = {
                                'id': str(notifications[0].id) if hasattr(notifications[0], 'id') else None,
                                'title': f"New message from {message.sender.full_name or message.sender.email}",
                                'message': message.content[:100] if message.content else "",
                                'sender': {
                                    'id': message.sender.id,
                                    'full_name': message.sender.full_name or message.sender.email,
                                    'email': message.sender.email,
                                    'profile_photo_url': profile_photo_url,
                                },
                                'conversation_id': str(conversation.id) if conversation else None,
                                'created_at': message.timestamp.isoformat() if hasattr(message, 'timestamp') else None
                            }
                            await self.channel_layer.group_send(
                                notification_group_name,
                                {
                                    'type': 'new_notification',
                                    'notification': notification_data_payload
                                }
                            )
                            print(f"Sent new notification to user {recipient.id}")
                        except Exception as e:
                            print(f"Error sending notification to user {recipient.id}: {e}")
                            continue
                        
                except Exception as e:
                    print(f"Error processing recipient {recipient.id}: {e}")
                    # Continue with next recipient instead of failing completely
                    continue
                    
        except Exception as e:
            print(f"Error in broadcast_notifications: {e}")
            import traceback
            traceback.print_exc()

    @database_sync_to_async
    def get_unread_count_for_user(self, user):
        """Get unread count for a specific user"""
        try:
            from .models import Notification
            return Notification.objects.filter(recipient=user, is_read=False).count()
        except Exception as e:
            print(f"Error getting unread count for user {user.id}: {e}")
            return 0


class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        try:
            # Get user from middleware (already authenticated via JWT)
            self.user = self.scope.get('user')
            if not self.user or self.user.is_anonymous:
                await self.close()
                return
            
            self.user_id = str(self.user.id)
            self.notification_group_name = f'notifications_{self.user_id}'
            
            # Join notification group
            await self.channel_layer.group_add(
                self.notification_group_name,
                self.channel_name
            )
            
            await self.accept()
            
            # Send current unread count with error handling
            try:
                unread_count = await self.get_unread_count()
                await self.send(text_data=json.dumps({
                    'type': 'unread_count',
                    'count': unread_count
                }))
                print(f"NotificationConsumer connected for user {self.user.id}, unread count: {unread_count}")
            except Exception as e:
                print(f"Error sending initial unread count: {e}")
                # Don't disconnect, just log the error
                await self.send(text_data=json.dumps({
                    'type': 'unread_count',
                    'count': 0
                }))
        except Exception as e:
            print(f"Error in NotificationConsumer connect: {e}")
            await self.close()

    async def disconnect(self, close_code):
        # Leave notification group
        if hasattr(self, 'notification_group_name'):
            await self.channel_layer.group_discard(
                self.notification_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        # Handle any incoming messages (like marking notifications as read)
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')
            
            if message_type == 'mark_read':
                notification_id = text_data_json.get('notification_id')
                if notification_id:
                    success = await self.mark_notification_read(notification_id)
                    await self.send(text_data=json.dumps({
                        'type': 'notification_read',
                        'notification_id': notification_id,
                        'success': success
                    }))
                    
                    if success:
                        # Send updated unread count
                        unread_count = await self.get_unread_count()
                        await self.send(text_data=json.dumps({
                            'type': 'unread_count',
                            'count': unread_count
                        }))
                        
            elif message_type == 'get_unread_count':
                unread_count = await self.get_unread_count()
                await self.send(text_data=json.dumps({
                    'type': 'unread_count',
                    'count': unread_count
                }))
                
            elif message_type == 'get_notifications':
                limit = text_data_json.get('limit', 10)
                notifications = await self.get_recent_notifications(limit)
                await self.send(text_data=json.dumps({
                    'type': 'notifications_list',
                    'notifications': notifications
                }))
                
        except Exception as e:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'error': str(e)
            }))

    async def notification_update(self, event):
        # Send notification update to WebSocket
        try:
            await self.send(text_data=json.dumps(event['data']))
        except Exception as e:
            print(f"Error sending notification update: {e}")

    async def new_notification(self, event):
        # Send new notification to WebSocket
        try:
            await self.send(text_data=json.dumps({
                'type': 'new_notification',
                'notification': event['notification']
            }))
        except Exception as e:
            print(f"Error sending new notification: {e}")

    async def unread_count_update(self, event):
        # Send unread count update to WebSocket
        try:
            await self.send(text_data=json.dumps({
                'type': 'unread_count',
                'count': event['count']
            }))
        except Exception as e:
            print(f"Error sending unread count update: {e}")

    @database_sync_to_async
    def get_unread_count(self):
        from .models import Notification
        return Notification.objects.filter(recipient=self.user, is_read=False).count()

    @database_sync_to_async
    def mark_notification_read(self, notification_id):
        from .models import Notification
        try:
            notification = Notification.objects.get(id=notification_id, recipient=self.user)
            notification.mark_as_read()
            return True
        except ObjectDoesNotExist:
            return False
        except Exception as e:
            print(f"Error marking notification as read: {e}")
            return False

    @database_sync_to_async
    def get_recent_notifications(self, limit=10):
        from .models import Notification
        
        try:
            notifications = Notification.objects.filter(
                recipient=self.user
            ).select_related(
                'sender', 'conversation'
            ).order_by('-created_at')[:limit]
            
            # Serialize notifications
            serialized_notifications = []
            for notification in notifications:
                try:
                    serialized_notifications.append({
                        'id': str(notification.id),
                        'notification_type': notification.notification_type,
                        'title': notification.title,
                        'message': notification.message,
                        'sender': {
                            'id': notification.sender.id if notification.sender else None,
                            'full_name': notification.sender.full_name if notification.sender else None,
                            'email': notification.sender.email if notification.sender else None,
                        } if notification.sender else None,
                        'conversation': str(notification.conversation.id) if notification.conversation else None,
                        'conversation_name': self._get_conversation_name(notification.conversation) if notification.conversation else None,
                        'is_read': notification.is_read,
                        'read_at': notification.read_at.isoformat() if notification.read_at else None,
                        'created_at': notification.created_at.isoformat(),
                        'extra_data': notification.extra_data or {}
                    })
                except Exception as e:
                    print(f"Error serializing notification: {e}")
                    continue
            
            return serialized_notifications
            
        except Exception as e:
            print(f"Error getting recent notifications: {e}")
            return []
    
    def _get_conversation_name(self, conversation):
        """Helper method to get conversation display name"""
        try:
            if not conversation:
                return None
                
            if conversation.is_group:
                return conversation.name or "Group Chat"
            else:
                # For one-on-one chats, return the other participant's name
                other_participants = conversation.participants.exclude(id=self.user.id)
                if other_participants.exists():
                    return other_participants.first().full_name
                return "Chat"
        except Exception as e:
            print(f"Error getting conversation name: {e}")
            return "Chat"
