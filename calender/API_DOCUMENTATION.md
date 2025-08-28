# Calendar Availability System API Documentation

## Overview
This system allows users to set their availability with multiple time slots per day using URL parameters for easy access. All endpoints use bearer token authentication to identify the user.

## Models

### UserAvailability
Single model that handles all user availability settings:
- **Time Slots**: Individual status for Morning, Afternoon, Evening, Night slots
- **Repeat Schedule**: Once, Weekly, Monthly
- **Date Range**: Start date and end date
- **Notes**: Additional information

## API Endpoints

### 1. Create/Update Availability Settings
```
POST /api/calendar/availability/
PUT /api/calendar/availability/{id}/
```

**Request Body:**
```json
{
    "morning_available": true,
    "morning_status": "available",
    "afternoon_available": true,
    "afternoon_status": "maybe",
    "evening_available": false,
    "evening_status": "busy",
    "night_available": false,
    "night_status": "busy",
    "start_date": "2025-07-30",
    "repeat_schedule": "weekly",
    "notes": "Available mornings, maybe afternoons, busy evenings/nights"
}
```

### 2. Get Month Availability (with URL params)
```
GET /api/calendar/month/?year=2025&month=7
```

**Response:**
```json
{
    "year": 2025,
    "month": 7,
    "user": {
        "id": 1,
        "name": "John Doe"
    },
    "availability": [
        {
            "date": "2025-07-01",
            "day": 1,
            "time_slots": [
                {
                    "name": "Morning", 
                    "time": "8:00-12:00", 
                    "type": "morning",
                    "status": "available",
                    "status_display": "Available"
                },
                {
                    "name": "Afternoon", 
                    "time": "12:00-17:00", 
                    "type": "afternoon",
                    "status": "maybe",
                    "status_display": "Maybe"
                }
            ],
            "notes": "Available mornings, maybe afternoons",
            "availability_id": 1
        }
    ]
}
```

### 3. Get Day Availability (with URL params)
```
GET /api/calendar/day/?date=2025-07-30
```

**Response:**
```json
{
    "date": "2025-07-30",
    "time_slots": [
        {
            "name": "Morning", 
            "time": "8:00-12:00", 
            "type": "morning",
            "status": "available",
            "status_display": "Available"
        },
        {
            "name": "Evening", 
            "time": "17:00-20:00", 
            "type": "evening",
            "status": "maybe",
            "status_display": "Maybe"
        }
    ],
    "notes": "Available morning, maybe evening",
    "availability_id": 1
}
```

### 4. Quick Availability Update
```
POST /api/calendar/quick-update/
```

**Request Body:**
```json
{
    "date": "2025-07-30",
    "morning_available": true,
    "morning_status": "available",
    "afternoon_available": false,
    "afternoon_status": "busy",
    "evening_available": true,
    "evening_status": "maybe",
    "night_available": false,
    "night_status": "busy",
    "notes": "Available morning, maybe evening only"
}
```

### 5. Get User's All Availability Settings
```
GET /api/calendar/my-availability/
```

**Response:**
```json
[
    {
        "id": 1,
        "morning_available": true,
        "morning_status": "available",
        "morning_status_display": "Available",
        "afternoon_available": true,
        "afternoon_status": "maybe",
        "afternoon_status_display": "Maybe",
        "evening_available": false,
        "evening_status": "busy",
        "evening_status_display": "Busy",
        "night_available": false,
        "night_status": "busy",
        "night_status_display": "Busy",
        "available_time_slots": [
            {
                "name": "Morning", 
                "time": "8:00-12:00", 
                "type": "morning",
                "status": "available",
                "status_display": "Available"
            },
            {
                "name": "Afternoon", 
                "time": "12:00-17:00", 
                "type": "afternoon",
                "status": "maybe",
                "status_display": "Maybe"
            }
        ],
        "all_time_slots_with_status": {
            "morning": {
                "name": "Morning",
                "time": "8:00-12:00",
                "available": true,
                "status": "available",
                "status_display": "Available"
            },
            "afternoon": {
                "name": "Afternoon",
                "time": "12:00-17:00",
                "available": true,
                "status": "maybe",
                "status_display": "Maybe"
            },
            "evening": {
                "name": "Evening",
                "time": "17:00-20:00",
                "available": false,
                "status": "busy",
                "status_display": "Busy"
            },
            "night": {
                "name": "Night",
                "time": "20:00-22:00",
                "available": false,
                "status": "busy",
                "status_display": "Busy"
            }
        },
        "repeat_schedule": "weekly",
        "repeat_schedule_display": "Repeat weekly",
        "start_date": "2025-07-30",
        "end_date": "2025-08-06",
        "notes": "Weekday availability",
        "user_name": "John Doe",
        "created_at": "2025-07-30T10:00:00Z",
        "updated_at": "2025-07-30T10:00:00Z"
    }
]
```

## Time Slots Available

1. **Morning**: 8:00-12:00
2. **Afternoon**: 12:00-17:00  
3. **Evening**: 17:00-20:00
4. **Night**: 20:00-22:00

## Multiple Time Slot Selection Examples

### Single Time Slot
```json
{
    "morning_available": true,
    "afternoon_available": false,
    "evening_available": false,
    "night_available": false
}
```

### Two Time Slots
```json
{
    "morning_available": true,
    "afternoon_available": false,
    "evening_available": true,
    "night_available": false
}
```

### Three Time Slots
```json
{
    "morning_available": true,
    "afternoon_available": true,
    "evening_available": false,
    "night_available": true
}
```

### All Time Slots
```json
{
    "morning_available": true,
    "afternoon_available": true,
    "evening_available": true,
    "night_available": true
}
```

## URL Parameter Support

The system supports URL parameters for easy calendar navigation:

- **Month View**: `/api/calendar/month/?year=2025&month=7`
- **Day View**: `/api/calendar/day/?date=2025-07-30`
- **Year/Month**: Can be changed via URL parameters
- **Authentication**: Uses bearer token to identify the user automatically

This allows easy calendar navigation without needing to pass user IDs in the URL.
