"""Google Calendar services — backward-compatible re-exports.

The implementation has been split into focused modules:
- auth.py       → CalendarService singleton and credentials
- models.py     → Data classes (CalendarEvent, result types)
- helpers.py    → Validation, formatting, conflict detection, retry logic
- operations.py → CRUD operations (list_events, create_event, delete_event, update_event)

This file re-exports everything so existing imports continue to work.
"""

# Re-export operations (used by calendar.py)
from .operations import list_events, create_event, delete_event, update_event

# Re-export auth (used internally)
from .auth import CalendarService, calendar_service

# Re-export models (for anyone who needs the types)
from .models import (
    CalendarEvent,
    ListEventsResult,
    CreateEventResult,
    DeleteEventResult,
    UpdateEventResult,
)

# Re-export key helpers
from .helpers import (
    validate_iso_datetime,
    format_datetime_display,
    execute_request_async,
)