"""Shared helper utilities for Google Calendar operations.

Provides:
- Datetime validation and formatting
- Time conflict detection
- Attendee parsing and 403 fallback
- Contact info detection in descriptions
- Async request execution with retry logic
"""

import re
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any

from googleapiclient.http import HttpRequest
from googleapiclient.errors import HttpError

from siphon.config import get_logger
from siphon.config.timezone_utils import get_timezone, get_timezone_name
from .auth import calendar_service

logger = get_logger("google-calendar")


# ============================================================================
# CONSTANTS
# ============================================================================

MAX_RETRIES = 3
RETRY_DELAY_BASE = 1  # seconds
REQUEST_TIMEOUT = 15  # seconds

# Pre-compiled patterns for contact info detection
_PHONE_PATTERN = re.compile(r'[+]?\d{10,15}')
_EMAIL_PATTERN = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')


# ============================================================================
# DATETIME UTILITIES
# ============================================================================

def validate_iso_datetime(dt_string: str) -> Optional[datetime]:
    """Validate and parse an ISO 8601 datetime string."""
    try:
        return datetime.fromisoformat(dt_string.replace('Z', '+00:00'))
    except (ValueError, TypeError):
        return None


def normalize_to_local_tz(dt_string: str) -> Optional[datetime]:
    """Parse an ISO string, strip any hallucinated LLM timezones, and force local timezone.
    
    LLMs are bad at timezone math. They often generate the correct local time (e.g. 12:00) 
    but append 'Z' (UTC) or the wrong offset to the end of the string. 
    This function strips their offset completely, takes the naive date/time, and rigidly 
    applies the system's configured TIMEZONE.
    """
    dt = validate_iso_datetime(dt_string)
    if not dt:
        return None
        
    # Strip whatever timezone the LLM hallucinated, keeping just the raw yyyy-mm-dd hh:mm:ss
    naive_dt = dt.replace(tzinfo=None)
    
    # Force the strict local timezone from the environment
    local_tz = get_timezone()
    if local_tz is not None:
        return naive_dt.replace(tzinfo=local_tz)
    else:
        # Fallback to system local time if TIMEZONE env var is not set
        return naive_dt.astimezone()


def format_datetime_display(dt: datetime) -> tuple[str, str]:
    """Format a datetime for human display using the configured timezone.
    
    Returns:
        (formatted_string, timezone_name) tuple
    """
    display_tz = get_timezone()
    display_tz_name = get_timezone_name() or "local"
    
    if display_tz is not None:
        display_dt = dt.astimezone(display_tz)
        formatted = display_dt.strftime("%A, %B %d, %Y at %I:%M %p") + f" {display_tz_name}"
    else:
        display_dt = dt.astimezone()
        tz_name = display_dt.tzname() or "local"
        formatted = display_dt.strftime("%A, %B %d, %Y at %I:%M %p") + f" {tz_name}"
        display_tz_name = tz_name
    
    return formatted, display_tz_name


def get_default_time_min() -> tuple[str, str]:
    """Get the default timeMin (now) using the configured timezone.
    
    Returns:
        (iso_string, display_string) tuple
    """
    display_tz = get_timezone()
    if display_tz is not None:
        now = datetime.now(display_tz)
    else:
        now = datetime.now().astimezone()
    
    return now.isoformat(), now.strftime("%Y-%m-%d %H:%M %Z")


# ============================================================================
# VALIDATION HELPERS
# ============================================================================

def check_description_contact_info(description: Optional[str]) -> Optional[str]:
    """Check if description contains contact info. Returns a warning string if not."""
    if description:
        has_phone = _PHONE_PATTERN.search(description)
        has_email = _EMAIL_PATTERN.search(description)
        if not (has_phone or has_email):
            logger.warning("create_event: description missing contact info")
            return "WARNING: Description should include caller's contact info (phone or email) for identity verification."
    else:
        logger.warning("create_event: no description provided")
        return "WARNING: No description provided. Include caller's name and contact info for identity verification."
    return None


def parse_attendees(attendees: Optional[str]) -> List[Dict[str, str]]:
    """Parse comma-separated attendee emails into a list of dicts."""
    if not attendees:
        return []
    return [{"email": email.strip()} for email in attendees.split(",") if email.strip()]


# ============================================================================
# ASYNC REQUEST EXECUTION
# ============================================================================

async def execute_request_async(request: HttpRequest) -> Dict[str, Any]:
    """Execute Google API request asynchronously with timeout and retry logic.
    
    Handles:
    - Timeout with configurable limit
    - Exponential backoff on retries
    - Automatic retry on 429, 500, 502, 503, 504
    - Empty response handling (e.g., DELETE returns None)
    """
    loop = asyncio.get_event_loop()
    last_error = None
    
    for attempt in range(MAX_RETRIES):
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                result = await loop.run_in_executor(calendar_service._executor, request.execute)
            calendar_service.record_success()
            return result if result is not None else {}
        except TimeoutError:
            last_error = f"Request timed out after {REQUEST_TIMEOUT} seconds"
            logger.warning(f"Google API request timed out (attempt {attempt + 1}/{MAX_RETRIES})")
        except HttpError as e:
            if e.resp.status in [429, 500, 502, 503, 504]:
                last_error = f"HTTP {e.resp.status}: {e.reason}"
                logger.warning(f"Google API error (attempt {attempt + 1}/{MAX_RETRIES}): {last_error}")
            else:
                calendar_service.record_failure()
                raise
        except Exception as e:
            last_error = str(e)
            logger.warning(f"Google API request failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
        
        if attempt < MAX_RETRIES - 1:
            delay = RETRY_DELAY_BASE * (2 ** attempt)
            await asyncio.sleep(delay)
    
    calendar_service.record_failure()
    raise RuntimeError(f"Request failed after {MAX_RETRIES} attempts. Last error: {last_error}")


# ============================================================================
# CONFLICT DETECTION
# ============================================================================

async def check_time_conflicts(
    service, 
    start_iso: str, 
    end_iso: str, 
    exclude_event_id: Optional[str] = None
) -> Optional[str]:
    """Check for time conflicts in the given range.
    
    Returns error message string if conflicts found, None if slot is free.
    Swallows exceptions — conflict check is a safety net, not a blocker.
    """
    try:
        start_dt = validate_iso_datetime(start_iso)
        end_dt = validate_iso_datetime(end_iso)
        if not start_dt or not end_dt:
            return None
        
        conflict_request = service.events().list(
            calendarId=calendar_service.calendar_id,
            timeMin=start_dt.astimezone().isoformat(),
            timeMax=end_dt.astimezone().isoformat(),
            maxResults=10,
            singleEvents=True,
        )
        conflict_result = await execute_request_async(conflict_request)
        existing_events = conflict_result.get("items", [])
        
        if exclude_event_id:
            existing_events = [e for e in existing_events if e.get("id") != exclude_event_id]
        
        if existing_events:
            conflict_details = []
            for evt in existing_events[:3]:
                evt_start = evt.get("start", {}).get("dateTime", "unknown")
                evt_summary = evt.get("summary", "Untitled")
                conflict_details.append(f"  - {evt_summary} at {evt_start}")
            
            return (
                f"CONFLICT: Time slot is already booked!\n"
                f"Requested: {start_iso} to {end_iso}\n"
                f"Conflicting events:\n" + "\n".join(conflict_details) +
                "\n\nPlease choose a different time or check availability with list_events()."
            )
    except Exception as e:
        logger.warning(f"Conflict check failed (proceeding anyway): {e}")
    
    return None


# ============================================================================
# ATTENDEE FALLBACK
# ============================================================================

def _build_request(service, method: str, body: Dict[str, Any], 
                    event_id: Optional[str], send_updates: Optional[str]):
    """Build a Google Calendar API request."""
    if method == "insert":
        return service.events().insert(
            calendarId=calendar_service.calendar_id,
            body=body,
            sendUpdates=send_updates
        )
    elif method == "patch":
        return service.events().patch(
            calendarId=calendar_service.calendar_id,
            eventId=event_id,
            body=body,
            sendUpdates=send_updates
        )
    else:
        raise ValueError(f"Unknown method: {method}")


async def _fallback_without_email(service, method, body, event_id, attendees_raw):
    """Step 2: Keep attendees in body, but don't send email notifications"""
    logger.info("Retrying with attendees but without email notifications...")
    request = _build_request(service, method, body, event_id, send_updates=None)
    
    try:
        response = await execute_request_async(request)
        logger.info("Event created/updated with attendees (no email notification)")
        return {
            "response": response, 
            "attendee_note": "NOTE: Attendee was added to the event but email notification could not be sent."
        }
    except HttpError as e2:
        logger.warning(f"Step 2 also failed ({e2.resp.status}): {e2.reason}")
        return await _fallback_remove_attendees(service, method, body, event_id, attendees_raw)

async def _fallback_remove_attendees(service, method, body, event_id, attendees_raw):
    """Step 3: Last resort — remove attendees, save email in description"""
    logger.info("Falling back to saving email in description only...")
    body.pop("attendees", None)
    
    if attendees_raw and method == "insert":
        current_desc = body.get("description", "")
        if attendees_raw not in (current_desc or ""):
            body["description"] = (
                f"{current_desc}\nEmail: {attendees_raw}" 
                if current_desc else f"Email: {attendees_raw}"
            )
    
    request = _build_request(service, method, body, event_id, send_updates=None)
    response = await execute_request_async(request)
    
    note = "NOTE: Could not add attendee to event (service account limitation)."
    if attendees_raw:
        note += f" The email '{attendees_raw}' was saved in the event description."
    return {"response": response, "attendee_note": note}

async def execute_with_attendee_fallback(
    service,
    method: str,
    body: Dict[str, Any],
    attendee_list: List[Dict[str, str]],
    event_id: Optional[str] = None,
    attendees_raw: Optional[str] = None,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute a calendar API request with 3-step attendee fallback.
    
    Strategy (ensures attendees are added to the event whenever possible):
      Step 1: Try with attendees + sendUpdates="all" (full email notifications)
      Step 2: On 403 → keep attendees, drop sendUpdates (added to event, no email)
      Step 3: If step 2 also fails → remove attendees, save email in description
    
    Returns:
        Dict with 'response' (API response) and 'attendee_note' (optional warning)
    """
    # Step 1: Try with full notifications
    send_updates = "all" if attendee_list else None
    request = _build_request(service, method, body, event_id, send_updates)
    
    try:
        response = await execute_request_async(request)
        return {"response": response, "attendee_note": None}
    except HttpError as e:
        if not (e.resp.status == 403 and attendee_list):
            raise  # Not a 403 attendee issue — propagate
        
        logger.warning(f"403 on sendUpdates='all': {e.reason}")
        return await _fallback_without_email(service, method, body, event_id, attendees_raw)
