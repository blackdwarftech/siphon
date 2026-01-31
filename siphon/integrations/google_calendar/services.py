import os
import json
from google.oauth2.credentials import Credentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import HttpRequest
from datetime import datetime
from siphon.config import get_logger
from dotenv import load_dotenv
import asyncio
from functools import lru_cache
from typing import Optional

load_dotenv()

logger = get_logger("google-calendar")


class CalenderService:
    """Calendar Service with connection pooling and credential caching."""
    
    _instance = None
    _credentials = None
    _service = None
    
    def __new__(cls):
        """Singleton pattern for reusing service instance."""
        if cls._instance is None:
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
        """
        if self._service is not None:
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


# Singleton instance
calender_service = CalenderService()


# Pre-compile datetime validation for faster checks
def _validate_iso_datetime(dt_string: str) -> Optional[datetime]:
    """Fast datetime validation without exception overhead."""
    try:
        return datetime.fromisoformat(dt_string)
    except (ValueError, TypeError):
        return None


async def _execute_request_async(request: HttpRequest):
    """Execute Google API request asynchronously to avoid blocking."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, request.execute)


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
    """
    service = calender_service()
    if service is None:
        return "Unable to communicate with the Google Calendar Service."

    # Fast datetime validation
    if timeMin is None:
        timeMin = datetime.now().astimezone().isoformat()
    else:
        dt = _validate_iso_datetime(timeMin)
        if dt is None:
            return "timeMin in incorrect format. It should be in ISO format"
        timeMin = dt.astimezone().isoformat()

    if timeMax is not None:
        dt = _validate_iso_datetime(timeMax)
        if dt is None:
            return "timeMax in incorrect format. It should be in ISO format"
        timeMax = dt.astimezone().isoformat()

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

    # Execute asynchronously
    try:
        events_result = await _execute_request_async(request)
    except Exception as e:
        logger.error(f"Failed to list events: {e}")
        return "Failed to retrieve events from calendar."

    events = events_result.get("items", [])

    if not events:
        return "No upcoming events found."

    # Optimized event formatting with list comprehension
    events_info = []
    for i, event in enumerate(events):
        start = event["start"].get("dateTime", event["start"].get("date"))
        end = event["end"].get("dateTime", event["end"].get("date"))
        
        # Fast datetime formatting
        if start:
            start = datetime.fromisoformat(start).astimezone().strftime("%Y-%m-%d %H:%M:%S")
        if end:
            end = datetime.fromisoformat(end).astimezone().strftime("%Y-%m-%d %H:%M:%S")
        
        # Use f-string for faster formatting
        event_info = (
            f"index: {i + 1}\n"
            f"start: {start}\n"
            f"end: {end}\n"
            f"summary: {event.get('summary', 'N/A')}\n"
            f"description: {event.get('description', 'N/A')}\n"
            f"location: {event.get('location', 'N/A')}\n"
            f"event_id: {event.get('id', 'N/A')}"
        )
        events_info.append(event_info)

    return "\n--\n".join(events_info)


async def create_event(
    start: str,
    end: str,
    timeZone: str,
    summary: str | None = None,
    description: str | None = None,
    location: str | None = None,
) -> str:
    """
    Create a calendar event using the provided details.
    """
    service = calender_service()
    if service is None:
        return "Unable to communicate with the Google Calendar Service."

    # Fast datetime validation
    if not _validate_iso_datetime(start):
        return "Event start time not in ISO format"

    if not _validate_iso_datetime(end):
        return "Event end time not in ISO format"

    # Build event object efficiently
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

    # Execute asynchronously
    try:
        request = service.events().insert(
            calendarId=calender_service.calendar_id, 
            body=event
        )
        result = await _execute_request_async(request)
        return f"Event created with id {result.get('id')}"
    except Exception as e:
        logger.error(f"Failed to create event: {e}")
        return "Event could not be created."


async def delete_event(event_id: str) -> str:
    """
    Delete an event from the calendar.
    """
    service = calender_service()
    if service is None:
        return "Unable to communicate with the Google Calendar Service."

    try:
        request = service.events().delete(
            calendarId=calender_service.calendar_id, 
            eventId=event_id
        )
        await _execute_request_async(request)
        return f"Event with id {event_id} is deleted."
    except Exception as e:
        logger.error(f"Failed to delete event: {e}")
        return "Event could not be deleted."


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
    """
    service = calender_service()
    if service is None:
        return "Unable to communicate with the Google Calendar Service."
    
    updates = {}
    updated_params = []
    
    # Fast datetime validation
    if start is not None:
        if not _validate_iso_datetime(start):
            return "Event start time not in ISO format"
        updates['start'] = {'dateTime': start}
        updated_params.append("start")
        
    if end is not None:
        if not _validate_iso_datetime(end):
            return "Event end time not in ISO format"
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
    
    # Execute asynchronously
    try:
        request = service.events().patch(
            calendarId=calender_service.calendar_id, 
            eventId=event_id, 
            body=updates
        )
        await _execute_request_async(request)
        return f"Event with id {event_id} updated with [{', '.join(updated_params)}]"
    except Exception as e:
        logger.error(f"Failed to update event: {e}")
        return "Event could not be updated."