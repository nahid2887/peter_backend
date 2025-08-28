from django.core.management.base import BaseCommand
from chat.models import DefaultGroup


class Command(BaseCommand):
    help = 'Create conversations for default groups that don\'t have them'

    def handle(self, *args, **options):
        groups_without_conversations = DefaultGroup.objects.filter(
            conversation__isnull=True, 
            is_active=True
        )
        
        if not groups_without_conversations.exists():
            self.stdout.write(
                self.style.SUCCESS('All active default groups already have conversations!')
            )
            return
        
        created_count = 0
        for group in groups_without_conversations:
            conversation = group.get_or_create_conversation()
            created_count += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f'Created conversation for "{group.name}" (Group ID: {group.id}, Conversation ID: {conversation.id})'
                )
            )
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully created {created_count} conversations for default groups')
        )
