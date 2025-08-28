from django.core.management.base import BaseCommand
from django.db import models
from event.models import Event, EventResponse


class Command(BaseCommand):
    help = 'Clean up host responses from events - hosts should not have response records'

    def handle(self, *args, **options):
        # Find all events where the host has a response
        host_responses = EventResponse.objects.filter(
            event__host=models.F('user')
        ).select_related('event', 'user')
        
        count = host_responses.count()
        
        if count == 0:
            self.stdout.write(
                self.style.SUCCESS('No host responses found. Database is clean.')
            )
            return
        
        # Show what we're going to delete
        self.stdout.write(f'Found {count} host responses to clean up:')
        for response in host_responses:
            self.stdout.write(
                f'  - Event "{response.event.title}" (ID: {response.event.id}): '
                f'Host {response.user.full_name} (ID: {response.user.id}) - {response.response}'
            )
        
        # Ask for confirmation
        confirm = input('\nDo you want to delete these host responses? (yes/no): ')
        if confirm.lower() in ['yes', 'y']:
            # Delete the host responses
            deleted_count = host_responses.delete()[0]
            self.stdout.write(
                self.style.SUCCESS(f'Successfully deleted {deleted_count} host responses.')
            )
        else:
            self.stdout.write('Operation cancelled.')
