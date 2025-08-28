# Example usage of UserAvailability model with individual time slot status

"""
Examples showing how users can save individual time slot availability:

Example 1: Morning Available, Other slots Not Available
{
    "morning_available": true,
    "morning_status": "available",
    "afternoon_available": false,
    "afternoon_status": "busy",
    "evening_available": false,
    "evening_status": "busy",
    "night_available": false,
    "night_status": "busy",
    "start_date": "2025-07-30",
    "repeat_schedule": "weekly"
}

Example 2: Multiple slots with different statuses
{
    "morning_available": true,
    "morning_status": "available",
    "afternoon_available": true,
    "afternoon_status": "maybe",
    "evening_available": false,
    "evening_status": "busy",
    "night_available": true,
    "night_status": "available",
    "start_date": "2025-07-30",
    "repeat_schedule": "weekly"
}

Example 3: Individual slot status - some available, some busy
{
    "morning_available": true,
    "morning_status": "available",
    "afternoon_available": false,
    "afternoon_status": "busy",
    "evening_available": true,
    "evening_status": "maybe",
    "night_available": false,
    "night_status": "busy",
    "start_date": "2025-07-30",
    "repeat_schedule": "once"
}

get_available_time_slots() will return:
Example 1: [
    {
        'name': 'Morning', 
        'time': '8:00-12:00', 
        'type': 'morning',
        'status': 'available',
        'status_display': 'Available'
    }
]

Example 2: [
    {
        'name': 'Morning', 
        'time': '8:00-12:00', 
        'type': 'morning',
        'status': 'available',
        'status_display': 'Available'
    },
    {
        'name': 'Afternoon', 
        'time': '12:00-17:00', 
        'type': 'afternoon',
        'status': 'maybe',
        'status_display': 'Maybe'
    },
    {
        'name': 'Night', 
        'time': '20:00-22:00', 
        'type': 'night',
        'status': 'available',
        'status_display': 'Available'
    }
]

get_all_time_slots_with_status() will return all slots:
{
    'morning': {
        'name': 'Morning',
        'time': '8:00-12:00',
        'available': true,
        'status': 'available',
        'status_display': 'Available'
    },
    'afternoon': {
        'name': 'Afternoon',
        'time': '12:00-17:00',
        'available': false,
        'status': 'busy',
        'status_display': 'Busy'
    },
    'evening': {
        'name': 'Evening',
        'time': '17:00-20:00',
        'available': false,
        'status': 'busy',
        'status_display': 'Busy'
    },
    'night': {
        'name': 'Night',
        'time': '20:00-22:00',
        'available': false,
        'status': 'busy',
        'status_display': 'Busy'
    }
}
"""

# API Usage Examples with Individual Time Slot Status:

# POST /api/calendar/availability/
# Create availability with individual time slot statuses
individual_slot_example = {
    "morning_available": True,
    "morning_status": "available",
    "afternoon_available": True,
    "afternoon_status": "maybe",
    "evening_available": False,
    "evening_status": "busy",
    "night_available": False,
    "night_status": "busy",
    "start_date": "2025-07-30",
    "repeat_schedule": "weekly",
    "notes": "Available mornings, maybe afternoons, busy evenings/nights"
}

# POST /api/calendar/quick-update/
# Quick update with individual time slot status
quick_update_individual = {
    "date": "2025-07-30",
    "morning_available": True,
    "morning_status": "available",
    "afternoon_available": False,
    "afternoon_status": "busy",
    "evening_available": True,
    "evening_status": "maybe",
    "night_available": False,
    "night_status": "busy",
    "notes": "Morning available, afternoon busy, evening maybe, night busy"
}
