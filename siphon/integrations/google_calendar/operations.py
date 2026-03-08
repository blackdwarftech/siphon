"""Google Calendar CRUD operations.

All operations return structured LLM-friendly message strings.
Each function handles its own error cases and returns consistent SUCCESS/ERROR responses.
"""

from datetime import datetime
from typing import Optional

from googleapiclient.errors import HttpError

from siphon.config import get_logger
from siphon.config.timezone_utils import get_timezone_name
from .auth import calendar_service
from .models import (
    CalendarEvent,
    ListEventsResult,
    CreateEventResult,
    DeleteEventResult,
    UpdateEventResult,
)
from .helpers import (
    validate_iso_datetime,
    normalize_to_local_tz,
    format_datetime_display,
    get_default_time_min,
    check_description_contact_info,
    parse_attendees,
    execute_request_async,
    check_time_conflicts,
    execute_with_attendee_fallback,
)

logger = get_logger("google-calendar")


# ============================================================================
# LIST EVENTS
# ============================================================================

async def list_events(
    summary: str | None = None,
    description: str | None = None,
    location: str | None = None,
    timeMin: str | None = None,
    timeMax: str | None = None,
    maxResults: int = 10,
) -> str:
    """
    Retrieve calendar events based on specified filters.
    Returns a structured message for the LLM with clear success/failure status.
    
    IMPORTANT FOR LLM:
    - ALWAYS call get_current_datetime() BEFORE this function to know current time
    - Use timeMin to set the start of your search range (default: now)
    - Use timeMax to limit how far ahead to search
    - Each event includes an event_id needed for update/delete operations
    """
    result = ListEventsResult(success=False)
    
    service = calendar_service()
    if service is None:
        result.error = "Calendar service not available. Check GOOGLE_CALENDAR_CREDENTIALS_PATH."
        return result.to_llm_message()

    # Handle timeMin — use configured timezone for default
    if timeMin is None:
        time_min_iso, search_range_start = get_default_time_min()
        timeMin = time_min_iso
        result.search_range_start = search_range_start
    else:
        dt = validate_iso_datetime(timeMin)
        if dt is None:
            result.error = f"Invalid timeMin format. Expected ISO 8601, got: {timeMin}"
            return result.to_llm_message()
        timeMin = dt.astimezone().isoformat()
        result.search_range_start = dt.astimezone().strftime("%Y-%m-%d %H:%M %Z")

    # Handle timeMax
    if timeMax is not None:
        dt = validate_iso_datetime(timeMax)
        if dt is None:
            result.error = f"Invalid timeMax format. Expected ISO 8601, got: {timeMax}"
            return result.to_llm_message()
        timeMax = dt.astimezone().isoformat()
        result.search_range_end = dt.astimezone().strftime("%Y-%m-%d %H:%M %Z")

    # Cap maxResults
    try:
        maxResults = min(int(maxResults), 50)
    except (ValueError, TypeError):
        maxResults = 10

    # Build search query
    search_params = [x for x in [summary, description, location] if x]
    search_query = " ".join(search_params).lower() if search_params else None

    # Execute primary search using Google's native 'q' parameter first
    request = service.events().list(
        calendarId=calendar_service.calendar_id,
        timeMin=timeMin,
        timeMax=timeMax,
        maxResults=maxResults,
        singleEvents=True,
        orderBy="startTime",
        q=search_query,
    )

    try:
        events_result = await execute_request_async(request)
        events = events_result.get("items", [])
    except Exception as e:
        logger.error(f"Failed to list events: {e}")
        result.error = str(e)
        return result.to_llm_message()

    # Fallback to client-side filtering if no events found AND there was a search query.
    # Google's search index can take several minutes to update, causing newly created
    # events to be "invisible" to native searches immediately after booking.
    if not events and search_query:
        import re
        search_terms = search_query.split()
        
        # Extract strong identifiers (emails or phone numbers)
        # Emails: contains '@' and '.'
        # Phones: contains '+' and digits, or just a bunch of digits (length >= 7)
        strong_identifiers = [
            term for term in search_terms 
            if ('@' in term and '.' in term) or (re.sub(r'[^0-9+]', '', term) and len(re.sub(r'[^0-9+]', '', term)) >= 7)
        ]

        # If strong identifiers are present, LLM is searching for a specific user.
        # Override any hallucinated time constraints to search all upcoming events.
        fallback_time_min = timeMin
        fallback_time_max = timeMax
        if strong_identifiers:
            logger.info("Strong identifier detected in search query. Overriding time filters to search all upcoming events.")
            fallback_time_min, _ = get_default_time_min()
            fallback_time_max = None

        logger.info(f"No events found via native search for '{search_query}'. Falling back to client-side filtering...")
        fallback_request = service.events().list(
            calendarId=calendar_service.calendar_id,
            timeMin=fallback_time_min,
            timeMax=fallback_time_max,
            maxResults=250, # Fetch more items to filter client-side
            singleEvents=True,
            orderBy="startTime",
        )
        
        try:
            fallback_result = await execute_request_async(fallback_request)
            fallback_events = fallback_result.get("items", [])
            
            filtered_events = []
            for event in fallback_events:
                # Combine all searchable fields into one lowercase string
                searchable_text = " ".join(filter(None, [
                    event.get("summary", ""),
                    event.get("description", ""),
                    event.get("location", ""),
                    " ".join([a.get("email", "") for a in event.get("attendees", [])])
                ])).lower()
                
                if strong_identifiers:
                    # If the query contained an email or phone, check if ANY of those match.
                    # This makes it highly robust against the LLM adding unnecessary noise (like "Reason:...")
                    if any(identifier in searchable_text for identifier in strong_identifiers):
                        filtered_events.append(event)
                else:
                    # Clean out common LLM hallucinated labels, then require all remaining words to match
                    clean_terms = [t for t in search_terms if t not in ['patient', 'name:', 'phone', 'number:', 'email:', 'reason:', 'appointment']]
                    if not clean_terms:
                        clean_terms = search_terms # If it was literally just "appointment", fallback
                        
                    if all(term in searchable_text for term in clean_terms):
                        filtered_events.append(event)
            
            # Trim to originally requested maxResults
            events = filtered_events[:maxResults]
            if events:
                logger.info(f"Fallback search found {len(events)} matching event(s).")
                
        except Exception as e:
            logger.error(f"Failed to execute fallback list events: {e}")

    result.success = True
    result.total_count = len(events)

    # Convert to structured events
    for event in events:
        start_raw = event["start"].get("dateTime", event["start"].get("date"))
        end_raw = event["end"].get("dateTime", event["end"].get("date"))
        
        tz_name = "UTC"
        start_formatted = start_raw
        end_formatted = end_raw
        
        if start_raw:
            try:
                start_dt = datetime.fromisoformat(start_raw)
                start_formatted, tz_name = format_datetime_display(start_dt)
            except:
                pass
        
        if end_raw:
            try:
                end_dt = datetime.fromisoformat(end_raw)
                end_formatted, _ = format_datetime_display(end_dt)
            except:
                pass
        
        calendar_event = CalendarEvent(
            event_id=event.get("id", ""),
            summary=event.get("summary", "(No title)"),
            start=start_raw or "",
            end=end_raw or "",
            start_formatted=start_formatted,
            end_formatted=end_formatted,
            timezone=tz_name,
            description=event.get("description"),
            location=event.get("location"),
        )
        result.events.append(calendar_event)

    return result.to_llm_message()


# ============================================================================
# CREATE EVENT
# ============================================================================

async def create_event(
    start: str,
    end: str,
    timeZone: str, # This will be ignored and overwritten by system_tz_name
    summary: str | None = None,
    description: str | None = None,
    location: str | None = None,
    attendees: str | None = None,
) -> str:
    """
    Create a calendar event.
    Returns a structured message with full event details for confirmation.
    
    IMPORTANT FOR LLM:
    - ALWAYS call get_current_datetime() first
    - ALWAYS call list_events() first to check availability
    - start/end MUST be ISO 8601 with timezone offset
    - After creation, READ BACK details to the caller
    """
    result = CreateEventResult(success=False)
    
    service = calendar_service()
    if service is None:
        result.error = "Calendar service not available. Check GOOGLE_CALENDAR_CREDENTIALS_PATH."
        return result.to_llm_message()

    if not start or not end:
        result.error = "Start and end times are required"
        return result.to_llm_message()

    # Validate datetimes and normalize to local timezone
    start_dt = normalize_to_local_tz(start)
    if start_dt is None:
        result.error = f"Invalid start time format. Expected ISO 8601 (e.g., '2026-01-15T14:00:00+05:30'), got: {start}"
        return result.to_llm_message()

    end_dt = normalize_to_local_tz(end)
    if end_dt is None:
        result.error = f"Invalid end time format. Expected ISO 8601 (e.g., '2026-01-15T15:00:00+05:30'), got: {end}"
        return result.to_llm_message()
    
    if end_dt <= start_dt:
        result.error = f"End time ({end}) must be after start time ({start})"
        return result.to_llm_message()

    # ---------------------------------------------------------
    # System Override: Rigidly apply environment timezone
    # ---------------------------------------------------------
    system_tz_name = get_timezone_name() or "local"
    
    start_iso = start_dt.isoformat()
    end_iso = end_dt.isoformat()

    # Conflict detection
    conflict_error = await check_time_conflicts(service, start_iso, end_iso)
    if conflict_error:
        result.error = conflict_error
        logger.warning("create_event: conflict detected")
        return result.to_llm_message()

    # Check for contact info in description
    contact_warning = check_description_contact_info(description, attendees)

    # Build event body
    attendee_list = parse_attendees(attendees)
    
    event_body = {
        "start": {"dateTime": start_iso, "timeZone": system_tz_name},
        "end": {"dateTime": end_iso, "timeZone": system_tz_name},
    }
    if summary is not None:
        event_body["summary"] = summary
    if description is not None:
        event_body["description"] = description
    if location is not None:
        event_body["location"] = location
    
    if attendee_list:
        event_body["attendees"] = attendee_list
        logger.info(f"Adding {len(attendee_list)} attendee(s) to event")

    # Execute with attendee fallback
    try:
        exec_result = await execute_with_attendee_fallback(
            service, method="insert", body=event_body,
            attendee_list=attendee_list, attendees_raw=attendees,
            description=description,
        )
        
        response = exec_result["response"]
        attendee_note = exec_result["attendee_note"]
        
        result.success = True
        result.event_id = response.get("id")
        result.summary = response.get("summary", summary)
        result.start = response.get("start", {}).get("dateTime", start_iso)
        result.end = response.get("end", {}).get("dateTime", end_iso)
        result.timezone = system_tz_name
        result.start_formatted, _ = format_datetime_display(start_dt)
        result.end_formatted, _ = format_datetime_display(end_dt)
        
        logger.info(f"Event created successfully: {result.event_id}")
        
        msg = result.to_llm_message()
        if attendee_note:
            msg += f"\n\n{attendee_note}"
        if contact_warning:
            msg += f"\n\n{contact_warning}"
        return msg
        
    except HttpError as e:
        logger.error(f"HTTP error creating event: {e.resp.status} - {e.reason}")
        if e.resp.status == 404:
            result.error = "Calendar not found. Check GOOGLE_CALENDAR_ID."
        else:
            result.error = f"Google Calendar error: {e.reason}"
        return result.to_llm_message()
    except Exception as e:
        logger.error(f"Failed to create event: {e}")
        result.error = str(e)
        return result.to_llm_message()


# ============================================================================
# DELETE EVENT
# ============================================================================

async def delete_event(event_id: str) -> str:
    """
    Delete an event from the calendar.
    
    IMPORTANT FOR LLM:
    - You MUST have the event_id from a previous list_events call
    - Confirm with the caller BEFORE deleting
    """
    result = DeleteEventResult(success=False, event_id=event_id)
    
    if not event_id or not event_id.strip():
        result.error = "event_id is required and cannot be empty"
        return result.to_llm_message()
    
    service = calendar_service()
    if service is None:
        result.error = "Calendar service not available."
        return result.to_llm_message()

    try:
        request = service.events().delete(
            calendarId=calendar_service.calendar_id, 
            eventId=event_id
        )
        # DELETE returns empty body (HTTP 204) — execute_request_async handles None → {}
        await execute_request_async(request)
        result.success = True
        logger.info(f"Event deleted successfully: {event_id}")
        return result.to_llm_message()
    except HttpError as e:
        if e.resp.status == 404:
            result.error = f"Event not found: {event_id}"
        elif e.resp.status == 410:
            result.error = f"Event already deleted: {event_id}"
        else:
            result.error = f"Google Calendar error: {e.reason}"
        logger.error(f"Failed to delete event: {e}")
        return result.to_llm_message()
    except Exception as e:
        logger.error(f"Failed to delete event: {e}")
        result.error = str(e)
        return result.to_llm_message()


# ============================================================================
# UPDATE EVENT
# ============================================================================

async def update_event(
    event_id: str,
    start: str | None = None,
    end: str | None = None,
    timeZone: str | None = None, # This will be ignored and overwritten by system_tz_name
    summary: str | None = None,
    description: str | None = None,
    location: str | None = None,
    attendees: str | None = None,
) -> str:
    """
    Update an event by replacing specified fields.
    
    IMPORTANT FOR LLM:
    - You MUST have the event_id from list_events()
    - Only provide the fields you want to change
    - If changing time, check availability first
    - Confirm with the caller BEFORE updating
    """
    result = UpdateEventResult(success=False, event_id=event_id)
    
    if not event_id or not event_id.strip():
        result.error = "event_id is required and cannot be empty"
        return result.to_llm_message()
    
    service = calendar_service()
    if service is None:
        result.error = "Calendar service not available."
        return result.to_llm_message()
    
    updates = {}
    updated_params = []
    
    # ---------------------------------------------------------
    # System Override: Rigidly apply environment timezone
    # ---------------------------------------------------------
    system_tz_name = get_timezone_name() or "local"
    
    # Validate and add datetime fields
    if start is not None:
        start_dt = normalize_to_local_tz(start)
        if not start_dt:
            result.error = f"Invalid start time format. Expected ISO 8601, got: {start}"
            return result.to_llm_message()
        
        # We rewrite the hallucinated start string to our clean system local ISO
        updates['start'] = {
            'dateTime': start_dt.isoformat(),
            'timeZone': system_tz_name
        }
        updated_params.append("start")
        
    if end is not None:
        end_dt = normalize_to_local_tz(end)
        if not end_dt:
            result.error = f"Invalid end time format. Expected ISO 8601, got: {end}"
            return result.to_llm_message()
            
        # We rewrite the hallucinated end string to our clean system local ISO
        updates['end'] = {
            'dateTime': end_dt.isoformat(),
            'timeZone': system_tz_name
        }
        updated_params.append("end")
        
    # We deliberately ignore `timeZone` coming from the LLM, as we enforce `system_tz_name`
    # above for any start/end updates.
    
    if summary is not None:
        updates["summary"] = summary
        updated_params.append("summary")
    if description is not None:
        updates["description"] = description
        updated_params.append("description")
    if location is not None:
        updates["location"] = location
        updated_params.append("location")
    
    attendee_list = parse_attendees(attendees)
    if attendee_list:
        updates["attendees"] = attendee_list
        updated_params.append("attendees")
        logger.info(f"Adding {len(attendee_list)} attendee(s) to event update")
    
    if not updates:
        result.error = "No fields provided to update"
        return result.to_llm_message()
    
    # Conflict detection for time changes
    if start is not None or end is not None:
        check_start = start
        check_end = end
        
        if check_start is None or check_end is None:
            try:
                get_request = service.events().get(
                    calendarId=calendar_service.calendar_id,
                    eventId=event_id
                )
                current_event = await execute_request_async(get_request)
                if check_start is None:
                    check_start = current_event.get("start", {}).get("dateTime")
                if check_end is None:
                    check_end = current_event.get("end", {}).get("dateTime")
            except Exception as e:
                logger.warning(f"Could not fetch current event for conflict check: {e}")
        
        if check_start and check_end:
            conflict_error = await check_time_conflicts(
                service, check_start, check_end, exclude_event_id=event_id
            )
            if conflict_error:
                result.error = conflict_error
                logger.warning("update_event: conflict detected")
                return result.to_llm_message()
    
    # Execute with attendee fallback
    try:
        exec_result = await execute_with_attendee_fallback(
            service, method="patch", body=updates,
            attendee_list=attendee_list, event_id=event_id,
            attendees_raw=attendees,
        )
        
        attendee_note = exec_result["attendee_note"]
        result.success = True
        result.updated_fields = updated_params
        logger.info(f"Event updated successfully: {event_id}")
        
        msg = result.to_llm_message()
        if attendee_note:
            msg += f"\n\n{attendee_note}"
        return msg
        
    except HttpError as e:
        if e.resp.status == 404:
            result.error = f"Event not found: {event_id}"
        else:
            result.error = f"Google Calendar error: {e.reason}"
        logger.error(f"Failed to update event: {e}")
        return result.to_llm_message()
    except Exception as e:
        logger.error(f"Failed to update event: {e}")
        result.error = str(e)
        return result.to_llm_message()
