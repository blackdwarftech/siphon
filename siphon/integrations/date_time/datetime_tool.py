from livekit.agents import function_tool
from datetime import datetime
from siphon.config.timezone_utils import get_timezone, get_timezone_name
from siphon.config import get_logger

logger = get_logger("date-time")


class DateTime:
    """Provides current date and time information to the agent."""
    
    def __init__(self) -> None:
        pass

    @function_tool()
    async def get_current_datetime(self) -> str:
        """
        Get the current date and time.
        Returns the current date and time in the configured timezone.
        """
        try:
            # Get configured timezone or use local time
            tz = get_timezone()
            tz_name = get_timezone_name() or "local time"
            
            if tz is not None:
                now = datetime.now(tz)
                logger.debug(f"Using timezone: {tz_name}")
            else:
                now = datetime.now()
                logger.debug("Using local timezone")
            
            # Full readable format with timezone
            if tz is not None:
                return now.strftime("%A, %B %d, %Y at %I:%M %p %Z")
            else:
                return now.strftime("%A, %B %d, %Y at %I:%M %p")
                
        except Exception as e:
            logger.error(f"Error getting current datetime: {e}", exc_info=True)
            return "Unable to get current date and time"
