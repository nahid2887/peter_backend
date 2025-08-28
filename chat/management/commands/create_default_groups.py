from django.core.management.base import BaseCommand
from chat.models import DefaultGroup


class Command(BaseCommand):
    help = 'Create default groups from the app requirements'

    def handle(self, *args, **options):
        # Default groups from the image
        default_groups = [
            {
                'name': 'Kindergarten',
                'description': 'Group for Kindergarten students and parents'
            },
            {
                'name': '1st Grade',
                'description': 'Group for 1st Grade students and parents'
            },
            {
                'name': '2nd Grade',
                'description': 'Group for 2nd Grade students and parents'
            },
            {
                'name': '3rd Grade',
                'description': 'Group for 3rd Grade students and parents'
            },
            {
                'name': '4th Grade',
                'description': 'Group for 4th Grade students and parents'
            },
            {
                'name': 'Soccer Team',
                'description': 'Group for Soccer Team members and parents'
            },
            {
                'name': 'Moms Group',
                'description': 'Group for mothers to connect and share'
            },
            {
                'name': 'Dads Group',
                'description': 'Group for fathers to connect and share'
            },
            {
                'name': 'Basketball',
                'description': 'Group for Basketball team members and parents'
            },
            {
                'name': 'Art Class',
                'description': 'Group for Art Class participants and parents'
            },
        ]

        created_count = 0
        updated_count = 0
        
        for group_data in default_groups:
            group, created = DefaultGroup.objects.get_or_create(
                name=group_data['name'],
                defaults={
                    'description': group_data['description'],
                    'is_active': True
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Created default group: {group.name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Default group already exists: {group.name}')
                )
            
            # Ensure conversation is created for this group
            if not group.conversation:
                conversation = group.get_or_create_conversation()
                updated_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Created conversation for: {group.name} (ID: {conversation.id})')
                )

        self.stdout.write(
            self.style.SUCCESS(f'Successfully processed {created_count} new groups and {updated_count} conversations')
        )
