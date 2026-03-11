"""Google Calendar authentication and service management.

Provides a singleton CalendarService with:
- Auto-detection of service account vs OAuth credentials
- Connection pooling and credential caching
- Thread safety and auto-recovery on consecutive failures
"""

import os
import json
import threading
from datetime import datetime
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor

from google.oauth2.credentials import Credentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from dotenv import load_dotenv

from siphon.config import get_logger

load_dotenv()

logger = get_logger("google-calendar")


class CalendarService:
    """Calendar Service singleton with connection pooling and auto-recovery."""
    
    _instance = None
    _credentials = None
    _service = None
    _lock = threading.Lock()
    _executor = ThreadPoolExecutor(max_workers=4)
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(CalendarService, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
            
        self._initialized = True
        self.__scope = ["https://www.googleapis.com/auth/calendar"]
        
        self.credentials_path = os.getenv(
            "GOOGLE_CALENDAR_CREDENTIALS_PATH", 
            "credentials.json"
        )
        self.token_path = os.getenv(
            "GOOGLE_CALENDAR_TOKEN_PATH", 
            "token.json"
        )
        self.calendar_id = os.getenv("GOOGLE_CALENDAR_ID", "primary")
        
        self._last_successful_call = None
        self._consecutive_failures = 0

    @lru_cache(maxsize=1)
    def _is_service_account_file(self, filepath):
        """Detect if the credentials file is a service account key."""
        try:
            with open(filepath, 'r') as f:
                cred_data = json.load(f)
                return cred_data.get('type') == 'service_account'
        except Exception:
            return False

    def _initialize_credentials(self):
        """Initialize credentials only once and cache them."""
        if self._credentials is not None:
            return self._credentials
            
        try:
            if not os.path.exists(self.credentials_path):
                self._log_missing_credentials_error()
                return None
            
            is_service_account = self._is_service_account_file(self.credentials_path)
            
            if is_service_account:
                creds = self._init_service_account()
            else:
                creds = self._init_oauth()

            self._credentials = creds
            logger.info("Credentials cached successfully")
            return creds
            
        except FileNotFoundError as e:
            logger.error(f"Credentials file not found: {e}")
            return None
        except Exception as e:
            logger.error(f"Credential initialization failed: {e}", exc_info=True)
            return None

    def _log_missing_credentials_error(self):
        logger.error(
            f"Credentials file not found: {self.credentials_path}\n\n"
            f"Setup Instructions:\n"
            f"1. Go to https://console.cloud.google.com/\n"
            f"2. Enable Google Calendar API\n"
            f"3. Create Service Account credentials\n"
            f"4. Download JSON key and save as {self.credentials_path}\n"
            f"5. Share your calendar with the service account email\n\n"
            f"Set GOOGLE_CALENDAR_CREDENTIALS_PATH in .env to use a different path"
        )

    def _init_service_account(self):
        logger.info("Using service account authentication")
        creds = ServiceAccountCredentials.from_service_account_file(
            self.credentials_path,
            scopes=self.__scope
        )
        logger.info("Service account authenticated successfully")
        return creds

    def _init_oauth(self):
        logger.info("Using OAuth authentication")
        creds = None
        
        if os.path.exists(self.token_path):
            logger.info(f"Loading OAuth token from {self.token_path}")
            creds = Credentials.from_authorized_user_file(
                self.token_path, self.__scope
            )

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logger.info("Refreshing expired OAuth token")
                creds.refresh(Request())
            else:
                logger.warning(
                    "OAuth flow required - opening browser. "
                    "This should only happen ONCE. "
                    "For production, use service account instead."
                )
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, self.__scope
                )
                creds = flow.run_local_server(port=0)

            logger.info(f"Saving OAuth token to {self.token_path}")
            with open(self.token_path, "w") as token:
                token.write(creds.to_json())
        return creds

    def __call__(self):
        """Returns a Calendar API service object with connection pooling and auto-recovery."""
        if self._service is not None:
            if self._consecutive_failures >= 3:
                logger.warning("Too many consecutive failures, reinitializing service")
                self._service = None
                self._credentials = None
                self._consecutive_failures = 0
            else:
                return self._service
            
        creds = self._initialize_credentials()
        if creds is None:
            return None
            
        try:
            self._service = build(
                "calendar", "v3", 
                credentials=creds,
                cache_discovery=False
            )
            logger.info("Calendar service initialized successfully")
            return self._service
        except Exception as e:
            logger.error(f"Calendar service initialization failed: {e}", exc_info=True)
            return None
    
    def record_success(self):
        self._last_successful_call = datetime.now()
        self._consecutive_failures = 0
    
    def record_failure(self):
        self._consecutive_failures += 1


# Singleton instance — import this to use the service
calendar_service = CalendarService()
