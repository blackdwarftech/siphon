from livekit.agents import RunContext, function_tool
from siphon.config import get_logger
from . import services

logger = get_logger("google-calendar")

class GoogleCalendar:
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
        """
        Retrieve a list of calendar events based on specified filters.

        This function queries the calendar for events that match the given criteria.
        All filter parameters are optional and can be used in combination to narrow
        down the results.

        Args:
            summary (str, optional): Filter events by their summary (title or subject).
            description (str, optional): Filter events by text found in the event description.
            location (str, optional): Filter events based on their location.
            timeMin (str, optional): ISO 8601 formatted lower time bound (exclusive)
                for filtering events by end time. Must be in local time and have timezone offset.
            timeMax (str, optional): ISO 8601 formatted upper time bound (exclusive)
                for filtering events by start time. Must be in local time and have timezone offset.
            maxResults (int, optional): Maximum number of events to return.

        Returns:
            list: A list of event objects that match the provided filters.
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
    ) -> str:
        """
        Creates a calendar event using the provided details.

        Args:
            start (str): Event start time in ISO 8601 format (e.g., '2025-04-06T10:00:00-07:00').
            end (str): Event end time in ISO 8601 format (e.g., '2025-04-06T11:00:00-07:00').
            timeZone (str): User timezone formatted as an IANA Time Zone Database name (e.g. "Europe/Zurich").
            summary (str): Short title or subject of the event.
            description (str, optional): Detailed description or notes for the event. Defaults to None.
            location (str, optional): Physical or virtual location of the event. Defaults to None.
        """
        return await services.create_event(
            start=start,
            end=end,
            timeZone=timeZone,
            summary=summary,
            description=description,
            location=location,
        )


    @function_tool()
    async def delete_event(self, event_id: str):
        """
        Deletes an event from the calender.

        Args:
            event_id: Event identifier.
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
    ):
        """
        Updates an event by replacing specified fields with new values.
        Any fields not included in the request will retain their existing values.

        Args:
            event_id (str): Event identifier.
            start (str, optional): Event start time in ISO 8601 format (e.g., '2025-04-06T10:00:00-04:00'). Defaults to None.
            end (str, optional): Event end time in ISO 8601 format (e.g., '2025-04-06T11:00:00-04:00'). Defaults to None.
            timeZone (str, optional): User timezone formatted as an IANA Time Zone Database name (e.g. "Europe/Zurich"). Defaults to None.
            summary (str, optional): Short title or subject of the event. Defaults to None.
            description (str, optional): Detailed description or notes for the event. Defaults to None.
            location (str, optional): Physical or virtual location of the event. Defaults to None.
        """
        return await services.update_event(
            event_id=event_id,
            start=start,
            end=end,
            timeZone=timeZone,
            summary=summary,
            description=description,
            location=location,
        )