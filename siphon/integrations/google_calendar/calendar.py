from livekit.agents import RunContext, function_tool
from siphon.config import get_logger
from . import services

logger = get_logger("google-calendar")

class GoogleCalendar:
    """Google Calendar integration for voice AI agents.
    
    Provides tools for listing, creating, updating, and deleting calendar events.
    All operations return structured messages with SUCCESS or ERROR status.
    """
    
    def __init__(self) -> None:
        pass

    @function_tool()
    async def list_events(
        self,
        summary: str | None = None,
        description: str | None = None,
        location: str | None = None,
        timeMin: str | None = None,
        timeMax: str | None = None,
        maxResults: int = 10,
    ) -> str:
        """List calendar events within a time range. Use this to check availability before booking.
        
        MANDATORY BEFORE CREATE_EVENT: Call get_current_datetime() first to know today's date,
        then call this function to check if a time slot is available.
        
        *** CRITICAL RESCHEDULING / CANCELLING WARNING ***
        If you are searching for an EXISTING appointment because the user wants to RESCHEDULE or CANCEL:
        - DO NOT set timeMin and timeMax to the NEW requested date! The existing appointment is not there yet!
        - Leave timeMin as default (or set it to today) to search all upcoming events.
        - Only use the `description` parameter exactly as instructed below to find the user's booking.
        
        Args:
            summary: Filter by event title (optional)
            description: Filter by text in description (optional). **CRITICAL**: Use ONLY the caller's phone number or email here. DO NOT pass full sentences or the entire original description block, as this will cause the search to fail.
            location: Filter by location (optional)
            timeMin: Start of search range in ISO 8601 format (e.g., "2026-01-15T09:00:00+05:30"). REQUIRED for accurate results when checking availability for NEW bookings.
            timeMax: End of search range in ISO 8601 format (e.g., "2026-01-15T18:00:00+05:30"). Optional.
            maxResults: Maximum events to return (default: 10, max: 50)
        
        Returns:
            A structured message with SUCCESS or ERROR status. Each event includes:
            - event_id: Required for update/delete operations
            - Title, start time, end time (formatted for reading)
            - Description and location if available
        
        Example correct usage:
            1. Call get_current_datetime() → "Thursday, January 15, 2026 at 10:00 AM IST"
            2. Call list_events(timeMin="2026-01-15T14:00:00+05:30", timeMax="2026-01-15T15:00:00+05:30")
            3. Check if the time slot is free before creating an event
        """
        return await services.list_events(
            summary=summary,
            description=description,
            location=location,
            timeMin=timeMin,
            timeMax=timeMax,
            maxResults=maxResults,
        )


    @function_tool()
    async def create_event(
        self,
        start: str,
        end: str,
        timeZone: str,
        summary: str,
        description: str | None = None,
        location: str | None = None,
        attendees: str | None = None,
    ) -> str:
        """Create a new calendar event. MANDATORY: Check availability with list_events() first.
        
        REQUIRED PRE-STEPS (follow this order):
        1. Call get_current_datetime() to get today's date and timezone
        2. Call list_events() to check if the requested time slot is available
        3. Only proceed with create_event if the slot is free
        
        Args:
            start: Event start time in ISO 8601 format with timezone offset.
                   Example: "2026-01-15T14:00:00+05:30" (January 15, 2026 at 2 PM IST)
            end: Event end time in ISO 8601 format with timezone offset.
                 Example: "2026-01-15T15:00:00+05:30" (January 15, 2026 at 3 PM IST)
            timeZone: IANA timezone name (e.g., "Asia/Kolkata", "America/New_York", "Europe/London")
            summary: Event title. Example: "Appointment - John Smith"
            description: Event details. MUST include caller's phone number for identification.
                        Example: "Patient Name: John Smith\nPhone: +919876543210\nReason: Cleaning"
            location: Physical or virtual location (optional)
            attendees: Email address(es) to invite. They will receive Google Calendar notification.
                      Can be single email or comma-separated. Example: "john@example.com" or "john@example.com, jane@example.com"
        
        Returns:
            A structured message with SUCCESS or ERROR status.
            On SUCCESS: Includes event_id, formatted times, and a reminder to read back details to caller.
            On ERROR: Includes specific error message (invalid format, time conflict, etc.)
        
        IMPORTANT: After successful creation, ALWAYS read back the event details to the caller
        for confirmation, including the date, time, and purpose.
        """
        return await services.create_event(
            start=start,
            end=end,
            timeZone=timeZone,
            summary=summary,
            description=description,
            location=location,
            attendees=attendees,
        )


    @function_tool()
    async def delete_event(self, event_id: str) -> str:
        """Delete a calendar event. You MUST have the event_id from a previous list_events call.
        
        REQUIRED PRE-STEP: Call list_events() first to find the event_id of the event to delete.
        
        Args:
            event_id: The unique identifier of the event to delete. 
                      You get this from list_events() results.
        
        Returns:
            A structured message with SUCCESS or ERROR status.
            On ERROR: Includes reason (event not found, permission denied, etc.)
        
        IMPORTANT: Always confirm with the caller BEFORE deleting an event.
        Read back the event details and ask for explicit confirmation.
        """
        return await services.delete_event(event_id=event_id)


    @function_tool()
    async def update_event(
        self,
        event_id: str,
        start: str | None = None,
        end: str | None = None,
        timeZone: str | None = None,
        summary: str | None = None,
        description: str | None = None,
        location: str | None = None,
        attendees: str | None = None,
    ) -> str:
        """Update an existing calendar event. You MUST have the event_id from list_events().
        
        REQUIRED PRE-STEPS for RESCHEDULING:
        1. Call list_events() to find the EXISTING event and get its event_id. 
           CRITICAL: Do NOT pass the *new* date into list_events() timeMin/timeMax. 
           Search using ONLY the caller's phone number or email to find their current booking.
        2. Once you have the event_id, call get_current_datetime() and list_events() again (this time using the NEW date in timeMin/timeMax) to check if the new slot is available.
        3. Confirm the changes with the caller before calling update_event.
        
        Args:
            event_id: The unique identifier of the event to update. REQUIRED.
                      Get this from list_events() results.
            start: New start time in ISO 8601 format (optional). Example: "2026-01-16T10:00:00+05:30"
            end: New end time in ISO 8601 format (optional). Example: "2026-01-16T11:00:00+05:30"
            timeZone: New IANA timezone name (optional). Example: "Asia/Kolkata"
            summary: New event title (optional)
            description: New description (optional)
            location: New location (optional)
            attendees: Email address(es) to invite. They will receive Google Calendar notification.
                      Can be single email or comma-separated. Example: "john@example.com"
        
        Returns:
            A structured message with SUCCESS or ERROR status.
            On SUCCESS: Lists which fields were updated.
            On ERROR: Includes specific error message.
        
        NOTE: Only provide the fields you want to change. Omitted fields keep their current values.
        """
        return await services.update_event(
            event_id=event_id,
            start=start,
            end=end,
            timeZone=timeZone,
            summary=summary,
            description=description,
            location=location,
            attendees=attendees,
        )