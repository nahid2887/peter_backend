from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from chat.models import Conversation, ConversationParticipant, Message
import uuid
from django.db import transaction

User = get_user_model()


class Command(BaseCommand):
    help = 'Create test data for chat functionality'

    def add_arguments(self, parser):
        parser.add_argument(
            '--users', 
            type=int, 
            default=3, 
            help='Number of test users to create'
        )
        parser.add_argument(
            '--conversations', 
            type=int, 
            default=2, 
            help='Number of test conversations to create'
        )

    def handle(self, *args, **options):
        self.stdout.write('Creating test data for chat...')
        
        # Create test users
        test_users = []
        for i in range(options['users']):
            email = f'testuser{i+1}@example.com'
            full_name = f'Test User {i+1}'
            
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'full_name': full_name,
                    'is_active': True
                }
            )
            
            if created:
                user.set_password('testpass123')
                user.save()
                self.stdout.write(f'Created user: {user.email}')
            else:
                self.stdout.write(f'User already exists: {user.email}')
            
            test_users.append(user)
        
        # Create test conversations
        with transaction.atomic():
            for i in range(options['conversations']):
                if i == 0:
                    # Create individual conversation
                    conversation = Conversation.objects.create(
                        conversation_type='individual'
                    )
                    
                    # Add first two users
                    ConversationParticipant.objects.create(
                        conversation=conversation,
                        user=test_users[0],
                        role='member'
                    )
                    ConversationParticipant.objects.create(
                        conversation=conversation,
                        user=test_users[1],
                        role='member'
                    )
                    
                    # Add some test messages
                    Message.objects.create(
                        conversation=conversation,
                        sender=test_users[0],
                        content='Hello! How are you?'
                    )
                    Message.objects.create(
                        conversation=conversation,
                        sender=test_users[1],
                        content='Hi there! I am doing great, thanks for asking!'
                    )
                    
                    self.stdout.write(f'Created individual conversation: {conversation.id}')
                
                else:
                    # Create group conversation
                    conversation = Conversation.objects.create(
                        conversation_type='group',
                        name=f'Test Group {i}',
                        description=f'This is test group number {i}'
                    )
                    
                    # Add all users to group
                    for j, user in enumerate(test_users):
                        role = 'admin' if j == 0 else 'member'
                        ConversationParticipant.objects.create(
                            conversation=conversation,
                            user=user,
                            role=role
                        )
                    
                    # Add system message
                    Message.objects.create(
                        conversation=conversation,
                        message_type='system',
                        content=f'{test_users[0].full_name} created the group'
                    )
                    
                    # Add some test messages
                    Message.objects.create(
                        conversation=conversation,
                        sender=test_users[0],
                        content='Welcome to our test group!'
                    )
                    Message.objects.create(
                        conversation=conversation,
                        sender=test_users[1],
                        content='Thanks for adding me!'
                    )
                    
                    self.stdout.write(f'Created group conversation: {conversation.id}')
        
        self.stdout.write('\n📋 Test Data Summary:')
        self.stdout.write(f'Users created: {len(test_users)}')
        self.stdout.write(f'Conversations created: {options["conversations"]}')
        
        self.stdout.write('\n🔑 Test User Credentials:')
        for user in test_users:
            self.stdout.write(f'Email: {user.email} | Password: testpass123')
        
        self.stdout.write('\n💬 Conversation IDs for WebSocket testing:')
        conversations = Conversation.objects.all()
        for conv in conversations:
            conv_type = conv.conversation_type.title()
            name = conv.name or f"{conv.participants.first().full_name}'s chat"
            self.stdout.write(f'{conv_type}: {conv.id} ({name})')
        
        self.stdout.write('\n✅ Test data created successfully!')
        self.stdout.write('\n🚀 Next steps:')
        self.stdout.write('1. Start the Django development server: python manage.py runserver')
        self.stdout.write('2. Open websocket_test.html in your browser')
        self.stdout.write('3. Use one of the conversation IDs above')
        self.stdout.write('4. Or run: python test_websocket.py')
