from django.core.management.base import BaseCommand
from datetime import time
from calender.models import TimeSlot


class Command(BaseCommand):
    help = 'Create default time slots'

    def handle(self, *args, **options):
        time_slots = [
            {
                'name': TimeSlot.MORNING,
                'start_time': time(8, 0),
                'end_time': time(12, 0),
            },
            {
                'name': TimeSlot.AFTERNOON,
                'start_time': time(12, 0),
                'end_time': time(17, 0),
            },
            {
                'name': TimeSlot.EVENING,
                'start_time': time(17, 0),
                'end_time': time(20, 0),
            },
            {
                'name': TimeSlot.NIGHT,
                'start_time': time(20, 0),
                'end_time': time(22, 0),
            },
        ]

        for slot_data in time_slots:
            time_slot, created = TimeSlot.objects.get_or_create(
                name=slot_data['name'],
                defaults={
                    'start_time': slot_data['start_time'],
                    'end_time': slot_data['end_time'],
                }
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully created time slot: {time_slot}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Time slot already exists: {time_slot}')
                )

        self.stdout.write(
            self.style.SUCCESS('Time slots setup completed!')
        )
