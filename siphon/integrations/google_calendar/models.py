"""Data models for Google Calendar operation results.

Structured result types ensure consistent, parseable responses for LLM consumption.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any


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
