from django.core.management.base import BaseCommand
from calender.models import TimeSlot
from datetime import time


class Command(BaseCommand):
    help = 'Create default time slots for availability'

    def handle(self, *args, **options):
        time_slots = [
            {
                'name': 'Morning',
                'start_time': time(8, 0),  # 8:00 AM
                'end_time': time(12, 0),   # 12:00 PM
            },
            {
                'name': 'Afternoon',
                'start_time': time(12, 0), # 12:00 PM
                'end_time': time(17, 0),   # 5:00 PM
            },
            {
                'name': 'Evening',
                'start_time': time(17, 0), # 5:00 PM
                'end_time': time(20, 0),   # 8:00 PM
            },
            {
                'name': 'Night',
                'start_time': time(20, 0), # 8:00 PM
                'end_time': time(22, 0),   # 10:00 PM
            },
        ]

        for slot_data in time_slots:
            time_slot, created = TimeSlot.objects.get_or_create(
                name=slot_data['name'],
                defaults={
                    'start_time': slot_data['start_time'],
                    'end_time': slot_data['end_time']
                }
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Created time slot: {time_slot}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Time slot already exists: {time_slot}')
                )

        self.stdout.write(
            self.style.SUCCESS('Successfully created/checked all time slots')
        )
