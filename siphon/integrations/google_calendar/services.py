import os
import json
import threading
from dataclasses import dataclass, field, asdict
from google.oauth2.credentials import Credentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import HttpRequest
from googleapiclient.errors import HttpError
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from siphon.config import get_logger
from siphon.config.timezone_utils import get_timezone, get_timezone_name
from dotenv import load_dotenv
import asyncio
from functools import lru_cache, wraps
from typing import Optional, List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

load_dotenv()

logger = get_logger("google-calendar")


@dataclass
class CalendarEvent:
    """Structured representation of a calendar event."""
    event_id: str
    summary: str
    start: str  # ISO 8601 format
    end: str    # ISO 8601 format
    start_formatted: str  # Human readable
    end_formatted: str    # Human readable
    timezone: str
    description: Optional[str] = None
    location: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ListEventsResult:
    """Structured result for list_events operation."""
    success: bool
    events: List[CalendarEvent] = field(default_factory=list)
    total_count: int = 0
    search_range_start: Optional[str] = None
    search_range_end: Optional[str] = None
    error: Optional[str] = None
    
    def to_llm_message(self) -> str:
        """Generate a clear, structured message for the LLM."""
        if not self.success:
            return f"ERROR: Failed to retrieve events. Reason: {self.error}"
        
        if self.total_count == 0:
            range_info = ""
            if self.search_range_start:
                range_info = f" (searched from {self.search_range_start}"
                if self.search_range_end:
                    range_info += f" to {self.search_range_end}"
                range_info += ")"
            return f"SUCCESS: No events found{range_info}."
        
        
        lines = [
            f"SUCCESS: Found {self.total_count} event(s):",
            ""
        ]
        for i, event in enumerate(self.events, 1):
            lines.append(f"Event #{i}:")
            lines.append(f"  ID: {event.event_id}")
            lines.append(f"  Title: {event.summary}")
            lines.append(f"  Start: {event.start_formatted} ({event.timezone})")
            lines.append(f"  End: {event.end_formatted}")
            if event.description:
                lines.append(f"  Description: {event.description}")
            if event.location:
                lines.append(f"  Location: {event.location}")
            lines.append("")
        
        
        return "\n".join(lines)


@dataclass
class CreateEventResult:
    """Structured result for create_event operation."""
    success: bool
    event_id: Optional[str] = None
    summary: Optional[str] = None
    start: Optional[str] = None
    end: Optional[str] = None
    start_formatted: Optional[str] = None
    end_formatted: Optional[str] = None
    timezone: Optional[str] = None
    error: Optional[str] = None
    
    def to_llm_message(self) -> str:
        """Generate a clear, structured message for the LLM."""
        if not self.success:
            return f"ERROR: Failed to create event. Reason: {self.error}"
        
        return (
            f"SUCCESS: Event created successfully!\n"
            f"  Event ID: {self.event_id}\n"
            f"  Title: {self.summary}\n"
            f"  Start: {self.start_formatted} ({self.timezone})\n"
            f"  End: {self.end_formatted}\n"
            f"\nCONFIRMATION: Please read back these details to the caller to confirm the booking."
        )


@dataclass
class DeleteEventResult:
    """Structured result for delete_event operation."""
    success: bool
    event_id: Optional[str] = None
    error: Optional[str] = None
    
    def to_llm_message(self) -> str:
        if not self.success:
            return f"ERROR: Failed to delete event. Reason: {self.error}"
        return f"SUCCESS: Event {self.event_id} has been deleted."


@dataclass
class UpdateEventResult:
    """Structured result for update_event operation."""
    success: bool
    event_id: Optional[str] = None
    updated_fields: List[str] = field(default_factory=list)
    error: Optional[str] = None
    
    def to_llm_message(self) -> str:
        if not self.success:
            return f"ERROR: Failed to update event. Reason: {self.error}"
        return f"SUCCESS: Event {self.event_id} updated. Changed fields: {', '.join(self.updated_fields)}"


class CalenderService:
    """Calendar Service with connection pooling, credential caching, and thread safety."""
    
    _instance = None
    _credentials = None
    _service = None
    _lock = threading.Lock()
    _executor = ThreadPoolExecutor(max_workers=4)
    
    def __new__(cls):
        """Singleton pattern for reusing service instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:  # Double-check locking
                    cls._instance = super(CalenderService, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
            
        self._initialized = True
        self.__scope = ["https://www.googleapis.com/auth/calendar"]
        
        # Get credential path from environment variable
        self.credentials_path = os.getenv(
            "GOOGLE_CALENDAR_CREDENTIALS_PATH", 
            "credentials.json"
        )
        self.token_path = os.getenv(
            "GOOGLE_CALENDAR_TOKEN_PATH", 
            "token.json"
        )

        # Get calendar ID (defaults to 'primary')
        self.calendar_id = os.getenv("GOOGLE_CALENDAR_ID", "primary")
        
        # Track service health
        self._last_successful_call = None
        self._consecutive_failures = 0

    @lru_cache(maxsize=1)
    def _is_service_account_file(self, filepath):
        """Detect if the credentials file is a service account key. Cached for performance."""
        try:
            with open(filepath, 'r') as f:
                cred_data = json.load(f)
                return cred_data.get('type') == 'service_account'
        except:
            return False

    def _initialize_credentials(self):
        """Initialize credentials only once and cache them."""
        if self._credentials is not None:
            return self._credentials
            
        try:
            # Check if credentials file exists
            if not os.path.exists(self.credentials_path):
                error_msg = (
                    f"Credentials file not found: {self.credentials_path}\n\n"
                    f"📋 Setup Instructions:\n\n"
                    f"1. Go to https://console.cloud.google.com/\n"
                    f"2. Enable Google Calendar API\n"
                    f"3. Create Service Account credentials\n"
                    f"4. Download JSON key and save as {self.credentials_path}\n"
                    f"5. Share your calendar with the service account email\n\n"
                    f"💡 Set GOOGLE_CALENDAR_CREDENTIALS_PATH in .env to use a different path\n"
                )
                logger.error(error_msg)
                return None
            
            # Auto-detect credential type
            is_service_account = self._is_service_account_file(self.credentials_path)
            
            if is_service_account:
                # Use Service Account (Default - No browser needed!)
                logger.info("Using service account authentication")
                creds = ServiceAccountCredentials.from_service_account_file(
                    self.credentials_path,
                    scopes=self.__scope
                )
                logger.info("Service account authenticated successfully")
            
            else:
                # Use OAuth (fallback - requires browser first time or token exists)
                logger.info("Using OAuth authentication")
                creds = None
                
                # Check if token file exists with saved credentials
                if os.path.exists(self.token_path):
                    logger.info(f"Loading OAuth token from {self.token_path}")
                    creds = Credentials.from_authorized_user_file(
                        self.token_path, self.__scope
                    )

                # If credentials don't exist or are invalid, get new ones
                if not creds or not creds.valid:
                    if creds and creds.expired and creds.refresh_token:
                        logger.info("Refreshing expired OAuth token")
                        creds.refresh(Request())
                    else:
                        logger.warning(
                            "⚠️ OAuth flow required - opening browser. "
                            "This should only happen ONCE. "
                            "For production, use service account instead."
                        )
                        # OAuth flow
                        flow = InstalledAppFlow.from_client_secrets_file(
                            self.credentials_path, self.__scope
                        )
                        creds = flow.run_local_server(port=0)

                    # Save the OAuth token for next time
                    logger.info(f"Saving OAuth token to {self.token_path}")
                    with open(self.token_path, "w") as token:
                        token.write(creds.to_json())

            self._credentials = creds
            logger.info("✅ Credentials cached successfully")
            return creds
            
        except FileNotFoundError as e:
            logger.error(f"Credentials file not found: {e}")
            return None
        except Exception as e:
            logger.error(f"Credential initialization failed: {e}", exc_info=True)
            return None

    def __call__(self):
        """
        Returns a Calendar API service object with connection pooling.
        Reuses the same service instance for better performance.
        Includes health check and auto-recovery.
        """
        if self._service is not None:
            # Health check: if too many consecutive failures, try to reinitialize
            if self._consecutive_failures >= 3:
                logger.warning("Too many consecutive failures, attempting service reinitialization")
                self._service = None
                self._credentials = None
                self._consecutive_failures = 0
            else:
                return self._service
            
        creds = self._initialize_credentials()
        if creds is None:
            return None
            
        try:
            # Build service with connection pooling (cache_discovery for faster builds)
            self._service = build(
                "calendar", 
                "v3", 
                credentials=creds,
                cache_discovery=False  # Faster initialization
            )
            logger.info("✅ Calendar service initialized successfully")
            return self._service
            
        except Exception as e:
            logger.error(f"Calendar service initialization failed: {e}", exc_info=True)
            return None
    
    def record_success(self):
        """Record a successful API call."""
        self._last_successful_call = datetime.now()
        self._consecutive_failures = 0
    
    def record_failure(self):
        """Record a failed API call."""
        self._consecutive_failures += 1


# Singleton instance
calender_service = CalenderService()


# Pre-compile datetime validation for faster checks
def _validate_iso_datetime(dt_string: str) -> Optional[datetime]:
    """Fast datetime validation without exception overhead."""
    try:
        return datetime.fromisoformat(dt_string)
    except (ValueError, TypeError):
        return None


# ============================================================================
# RETRY LOGIC
# ============================================================================

MAX_RETRIES = 3
RETRY_DELAY_BASE = 1  # seconds
REQUEST_TIMEOUT = 15  # seconds


async def _execute_request_async(request: HttpRequest, timeout: int = REQUEST_TIMEOUT) -> Dict[str, Any]:
    """Execute Google API request asynchronously with timeout and retry logic."""
    loop = asyncio.get_event_loop()
    last_error = None
    
    for attempt in range(MAX_RETRIES):
        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(calender_service._executor, request.execute),
                timeout=timeout
            )
            calender_service.record_success()
            return result
        except asyncio.TimeoutError:
            last_error = f"Request timed out after {timeout} seconds"
            logger.warning(f"Google API request timed out (attempt {attempt + 1}/{MAX_RETRIES})")
        except HttpError as e:
            if e.resp.status in [429, 500, 502, 503, 504]:
                # Retry on rate limiting and server errors
                last_error = f"HTTP {e.resp.status}: {e.reason}"
                logger.warning(f"Google API error (attempt {attempt + 1}/{MAX_RETRIES}): {last_error}")
            else:
                # Don't retry on client errors (4xx except 429)
                calender_service.record_failure()
                raise
        except Exception as e:
            last_error = str(e)
            logger.warning(f"Google API request failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
        
        # Wait before retry (exponential backoff)
        if attempt < MAX_RETRIES - 1:
            delay = RETRY_DELAY_BASE * (2 ** attempt)
            await asyncio.sleep(delay)
    
    
    # All retries failed
    calender_service.record_failure()
    raise Exception(f"Request failed after {MAX_RETRIES} attempts. Last error: {last_error}")


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
    - The result will clearly indicate SUCCESS or ERROR
    - Each event includes an event_id needed for update/delete operations
    """
    result = ListEventsResult(success=False)
    
    service = calender_service()
    if service is None:
        result.error = "Calendar service not available. Check GOOGLE_CALENDAR_CREDENTIALS_PATH."
        return result.to_llm_message()

    # Fast datetime validation
    search_range_start = None
    search_range_end = None
    
    if timeMin is None:
        timeMin = datetime.now().astimezone().isoformat()
        search_range_start = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    else:
        dt = _validate_iso_datetime(timeMin)
        if dt is None:
            result.error = f"Invalid timeMin format. Expected ISO 8601, got: {timeMin}"
            return result.to_llm_message()
        timeMin = dt.astimezone().isoformat()
        search_range_start = dt.astimezone().strftime("%Y-%m-%d %H:%M %Z")

    if timeMax is not None:
        dt = _validate_iso_datetime(timeMax)
        if dt is None:
            result.error = f"Invalid timeMax format. Expected ISO 8601, got: {timeMax}"
            return result.to_llm_message()
        timeMax = dt.astimezone().isoformat()
        search_range_end = dt.astimezone().strftime("%Y-%m-%d %H:%M %Z")

    # Ensure maxResults is integer
    try:
        maxResults = min(int(maxResults), 50)  # Cap at 50 for performance
    except (ValueError, TypeError):
        maxResults = 10

    # Build search query efficiently
    search_params = [x for x in [summary, description, location] if x]
    search_query = " ".join(search_params) if search_params else None

    # Build API request
    request = service.events().list(
        calendarId=calender_service.calendar_id,
        timeMin=timeMin,
        timeMax=timeMax,
        maxResults=maxResults,
        singleEvents=True,
        orderBy="startTime",
        q=search_query,
    )

    # Execute with retry logic
    try:
        events_result = await _execute_request_async(request)
    except Exception as e:
        logger.error(f"Failed to list events: {e}")
        result.error = str(e)
        return result.to_llm_message()

    events = events_result.get("items", [])
    result.success = True
    result.total_count = len(events)
    result.search_range_start = search_range_start
    result.search_range_end = search_range_end

    # Convert to structured events
    for event in events:
        start_raw = event["start"].get("dateTime", event["start"].get("date"))
        end_raw = event["end"].get("dateTime", event["end"].get("date"))
        
        # Parse and format
        tz_name = "UTC"
        start_formatted = start_raw
        end_formatted = end_raw
        
        # Get configured timezone for display (e.g., Asia/Kolkata for IST)
        display_tz = get_timezone()
        display_tz_name = get_timezone_name() or "local"
        
        if start_raw:
            try:
                start_dt = datetime.fromisoformat(start_raw)
                # Convert to configured timezone for display
                if display_tz is not None:
                    start_dt = start_dt.astimezone(display_tz)
                    tz_name = display_tz_name
                else:
                    start_dt = start_dt.astimezone()
                    tz_name = start_dt.tzname() or "local"
                start_formatted = start_dt.strftime("%A, %B %d, %Y at %I:%M %p") + f" {tz_name}"
            except:
                pass
        
        if end_raw:
            try:
                end_dt = datetime.fromisoformat(end_raw)
                # Convert to configured timezone for display
                if display_tz is not None:
                    end_dt = end_dt.astimezone(display_tz)
                else:
                    end_dt = end_dt.astimezone()
                end_formatted = end_dt.strftime("%A, %B %d, %Y at %I:%M %p") + f" {tz_name}"
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


async def create_event(
    start: str,
    end: str,
    timeZone: str,
    summary: str | None = None,
    description: str | None = None,
    location: str | None = None,
    attendees: str | None = None,
) -> str:
    """
    Create a calendar event using the provided details.
    Returns a structured message with full event details for confirmation.
    
    IMPORTANT FOR LLM:
    - ALWAYS call get_current_datetime() first to get current time
    - ALWAYS call list_events() first to check if the time slot is available
    - start and end MUST be in ISO 8601 format (e.g., "2026-01-15T14:00:00+05:30")
    - timeZone should be IANA format (e.g., "Asia/Kolkata", "America/New_York")
    - attendees: Email address to invite (they will receive Google Calendar notification)
    - After creation, READ BACK the details to the caller for confirmation
    """
    result = CreateEventResult(success=False)
    
    service = calender_service()
    if service is None:
        result.error = "Calendar service not available. Check GOOGLE_CALENDAR_CREDENTIALS_PATH."
        return result.to_llm_message()

    # Fast datetime validation with helpful error messages
    start_dt = _validate_iso_datetime(start)
    if start_dt is None:
        result.error = f"Invalid start time format. Expected ISO 8601 (e.g., '2026-01-15T14:00:00+05:30'), got: {start}"
        return result.to_llm_message()

    end_dt = _validate_iso_datetime(end)
    if end_dt is None:
        result.error = f"Invalid end time format. Expected ISO 8601 (e.g., '2026-01-15T15:00:00+05:30'), got: {end}"
        return result.to_llm_message()
    
    # Validate that end is after start
    if end_dt <= start_dt:
        result.error = f"End time ({end}) must be after start time ({start})"
        return result.to_llm_message()

    # CONFLICT DETECTION: Check if the time slot is already booked
    try:
        conflict_request = service.events().list(
            calendarId=calender_service.calendar_id,
            timeMin=start_dt.astimezone().isoformat(),
            timeMax=end_dt.astimezone().isoformat(),
            maxResults=10,
            singleEvents=True,
        )
        conflict_result = await _execute_request_async(conflict_request)
        existing_events = conflict_result.get("items", [])
        
        if existing_events:
            # Format the conflicting events for the error message
            conflict_details = []
            for evt in existing_events[:3]:  # Show max 3 conflicts
                evt_start = evt.get("start", {}).get("dateTime", "unknown")
                evt_summary = evt.get("summary", "Untitled")
                conflict_details.append(f"  - {evt_summary} at {evt_start}")
            
            result.error = (
                f"CONFLICT: Time slot is already booked!\n"
                f"Requested: {start} to {end}\n"
                f"Conflicting events:\n" + "\n".join(conflict_details) +
                "\n\nPlease choose a different time or check availability with list_events()."
            )
            logger.warning(f"create_event: conflict detected - {len(existing_events)} existing event(s)")
            return result.to_llm_message()
    except Exception as e:
        # Log but don't fail - conflict check is a safety net, not a blocker
        logger.warning(f"create_event: conflict check failed (proceeding anyway): {e}")

    # Security: Warn if description doesn't contain contact info for identity verification
    # This is critical for later identity verification when caller wants to modify/cancel
    contact_warning = None
    if description:
        # Check if description contains something that looks like contact info (phone or email)
        import re
        phone_pattern = r'[+]?\d{10,15}'
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        has_phone = re.search(phone_pattern, description)
        has_email = re.search(email_pattern, description)
        if not (has_phone or has_email):
            contact_warning = "WARNING: Description should include caller's contact info (phone or email) for identity verification."
            logger.warning(f"create_event: description missing contact info - identity verification will be harder")
    else:
        contact_warning = "WARNING: No description provided. Include caller's name and contact info for identity verification."
        logger.warning("create_event: no description - caller identity cannot be verified later")

    # Build event object
    event = {
        "start": {"dateTime": start, "timeZone": timeZone},
        "end": {"dateTime": end, "timeZone": timeZone},
    }

    # Add optional fields
    if summary is not None:
        event["summary"] = summary
    if description is not None:
        event["description"] = description
    if location is not None:
        event["location"] = location
    
    # Add attendees for email notifications
    if attendees is not None:
        # Parse attendees - can be single email or comma-separated
        attendee_list = [{"email": email.strip()} for email in attendees.split(",") if email.strip()]
        if attendee_list:
            event["attendees"] = attendee_list
            logger.info(f"Adding {len(attendee_list)} attendee(s) to event")

    # Execute with retry logic
    try:
        request = service.events().insert(
            calendarId=calender_service.calendar_id, 
            body=event,
            sendUpdates="all"  # Send email notifications to attendees
        )
        response = await _execute_request_async(request)
        
        # Populate result with created event details
        result.success = True
        result.event_id = response.get("id")
        result.summary = response.get("summary", summary)
        result.start = response.get("start", {}).get("dateTime", start)
        result.end = response.get("end", {}).get("dateTime", end)
        result.timezone = timeZone
        
        # Format for readability using configured timezone
        display_tz = get_timezone()
        display_tz_name = get_timezone_name() or "local"
        
        if display_tz is not None:
            start_display = start_dt.astimezone(display_tz)
            end_display = end_dt.astimezone(display_tz)
            result.start_formatted = start_display.strftime("%A, %B %d, %Y at %I:%M %p") + f" {display_tz_name}"
            result.end_formatted = end_display.strftime("%A, %B %d, %Y at %I:%M %p") + f" {display_tz_name}"
        else:
            result.start_formatted = start_dt.astimezone().strftime("%A, %B %d, %Y at %I:%M %p %Z")
            result.end_formatted = end_dt.astimezone().strftime("%A, %B %d, %Y at %I:%M %p %Z")
        
        logger.info(f"Event created successfully: {result.event_id}")
        
        # Add contact warning to success message if applicable
        if contact_warning:
            return result.to_llm_message() + f"\n\n{contact_warning}"
        return result.to_llm_message()
        
    except HttpError as e:
        logger.error(f"HTTP error creating event: {e.resp.status} - {e.reason}")
        result.error = f"Google Calendar error: {e.reason}"
        return result.to_llm_message()
    except Exception as e:
        logger.error(f"Failed to create event: {e}")
        result.error = str(e)
        return result.to_llm_message()


async def delete_event(event_id: str) -> str:
    """
    Delete an event from the calendar.
    Returns a structured message indicating success or failure.
    
    IMPORTANT FOR LLM:
    - You MUST have the event_id from a previous list_events call
    - Confirm with the caller BEFORE deleting
    - After deletion, confirm it was successful
    """
    result = DeleteEventResult(success=False, event_id=event_id)
    
    if not event_id or not event_id.strip():
        result.error = "event_id is required and cannot be empty"
        return result.to_llm_message()
    
    service = calender_service()
    if service is None:
        result.error = "Calendar service not available."
        return result.to_llm_message()

    try:
        request = service.events().delete(
            calendarId=calender_service.calendar_id, 
            eventId=event_id
        )
        await _execute_request_async(request)
        result.success = True
        logger.info(f"Event deleted successfully: {event_id}")
        return result.to_llm_message()
    except HttpError as e:
        if e.resp.status == 404:
            result.error = f"Event not found: {event_id}"
        else:
            result.error = f"Google Calendar error: {e.reason}"
        logger.error(f"Failed to delete event: {e}")
        return result.to_llm_message()
    except Exception as e:
        logger.error(f"Failed to delete event: {e}")
        result.error = str(e)
        return result.to_llm_message()


async def update_event(
    event_id: str,
    start: str | None = None,
    end: str | None = None,
    timeZone: str | None = None,
    summary: str | None = None,
    description: str | None = None,
    location: str | None = None,
) -> str:
    """
    Update an event by replacing specified fields with new values.
    Returns a structured message indicating success or failure.
    
    IMPORTANT FOR LLM:
    - You MUST have the event_id from a previous list_events call
    - Only provide the fields you want to change
    - If changing time, call list_events() first to check availability
    - Confirm with the caller BEFORE updating
    """
    result = UpdateEventResult(success=False, event_id=event_id)
    
    if not event_id or not event_id.strip():
        result.error = "event_id is required and cannot be empty"
        return result.to_llm_message()
    
    service = calender_service()
    if service is None:
        result.error = "Calendar service not available."
        return result.to_llm_message()
    
    updates = {}
    updated_params = []
    
    # Fast datetime validation
    if start is not None:
        if not _validate_iso_datetime(start):
            result.error = f"Invalid start time format. Expected ISO 8601, got: {start}"
            return result.to_llm_message()
        updates['start'] = {'dateTime': start}
        updated_params.append("start")
        
    if end is not None:
        if not _validate_iso_datetime(end):
            result.error = f"Invalid end time format. Expected ISO 8601, got: {end}"
            return result.to_llm_message()
        updates['end'] = {'dateTime': end}
        updated_params.append("end")
        
    if timeZone is not None:
        if "start" not in updates:
            updates["start"] = {}
        updates['start']['timeZone'] = timeZone
        
        if "end" not in updates:
            updates["end"] = {}
        updates['end']['timeZone'] = timeZone
        
        if "start" not in updated_params:
            updated_params.append("start")
        if "end" not in updated_params:
            updated_params.append("end")
    
    # Add optional fields
    if summary is not None:
        updates["summary"] = summary
        updated_params.append("summary")
    if description is not None:
        updates["description"] = description
        updated_params.append("description")
    if location is not None:
        updates["location"] = location
        updated_params.append("location")
    
    if not updates:
        result.error = "No fields provided to update"
        return result.to_llm_message()
    
    # CONFLICT DETECTION: If changing time, check if new slot is available
    if start is not None or end is not None:
        try:
            # Determine the time range to check
            check_start = start if start else None
            check_end = end if end else None
            
            # If only one is provided, we need to get the current event to find the other
            if check_start is None or check_end is None:
                get_request = service.events().get(
                    calendarId=calender_service.calendar_id,
                    eventId=event_id
                )
                current_event = await _execute_request_async(get_request)
                
                if check_start is None:
                    check_start = current_event.get("start", {}).get("dateTime")
                if check_end is None:
                    check_end = current_event.get("end", {}).get("dateTime")
            
            if check_start and check_end:
                start_dt = _validate_iso_datetime(check_start)
                end_dt = _validate_iso_datetime(check_end)
                
                if start_dt and end_dt:
                    conflict_request = service.events().list(
                        calendarId=calender_service.calendar_id,
                        timeMin=start_dt.astimezone().isoformat(),
                        timeMax=end_dt.astimezone().isoformat(),
                        maxResults=10,
                        singleEvents=True,
                    )
                    conflict_result = await _execute_request_async(conflict_request)
                    existing_events = conflict_result.get("items", [])
                    
                    # Filter out the event being updated (it will appear in the list)
                    conflicting_events = [e for e in existing_events if e.get("id") != event_id]
                    
                    if conflicting_events:
                        conflict_details = []
                        for evt in conflicting_events[:3]:
                            evt_start = evt.get("start", {}).get("dateTime", "unknown")
                            evt_summary = evt.get("summary", "Untitled")
                            conflict_details.append(f"  - {evt_summary} at {evt_start}")
                        
                        result.error = (
                            f"CONFLICT: New time slot is already booked!\n"
                            f"Requested: {check_start} to {check_end}\n"
                            f"Conflicting events:\n" + "\n".join(conflict_details) +
                            "\n\nPlease choose a different time or check availability with list_events()."
                        )
                        logger.warning(f"update_event: conflict detected - {len(conflicting_events)} existing event(s)")
                        return result.to_llm_message()
        except Exception as e:
            # Log but don't fail - conflict check is a safety net
            logger.warning(f"update_event: conflict check failed (proceeding anyway): {e}")
    
    # Execute with retry logic
    try:
        request = service.events().patch(
            calendarId=calender_service.calendar_id, 
            eventId=event_id, 
            body=updates
        )
        await _execute_request_async(request)
        result.success = True
        result.updated_fields = updated_params
        logger.info(f"Event updated successfully: {event_id}")
        return result.to_llm_message()
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