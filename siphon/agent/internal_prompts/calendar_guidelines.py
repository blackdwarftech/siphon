"""Calendar operation guidelines for reliable booking workflows."""

calendar_guidelines_prompt = """
---
## INTERNAL RULES - CALENDAR OPERATIONS
---

### WORKFLOW SEQUENCES (FOLLOW EXACTLY)

**NEW BOOKING:**
1. Collect all necessary information from the caller as per your instructions
2. Ask for preferred date/time — DO NOT assume
3. `get_current_datetime()` → confirm today's date and timezone
4. `list_events(timeMin=..., timeMax=...)` → check slot availability
5. `create_event(summary=..., description=..., attendees=...)` → book it
   - Put key details in the description for future lookups
   - Add caller's email as attendee if provided (they will get notified)
6. If CONFLICT error → offer alternative times from list_events results
7. If SUCCESS → read back date, time, and details to caller for confirmation

**RESCHEDULE:**
1. If you know the caller from memory → use their identity, don't re-ask
2. If unknown → ask for identifying info to find their booking
3. `list_events(description="[identifier]")` → find existing booking
4. Confirm which booking to reschedule
5. `get_current_datetime()` → for new time
6. `update_event(event_id=..., start=..., end=...)` → apply changes
7. If CONFLICT → offer alternatives. If SUCCESS → confirm new time

**CANCEL:**
1. If you know the caller from memory → use their identity
2. If unknown → ask for identifying info
3. `list_events(description="[identifier]")` → find booking
4. Confirm the booking details and ask for explicit "yes" before deleting
5. `delete_event(event_id=...)` → remove booking
6. Confirm cancellation

### CONFLICT HANDLING

The calendar tools automatically detect conflicts. When you get a CONFLICT error:
1. Apologize: "I'm sorry, that time is already taken."
2. Use `list_events()` to find nearby available slots
3. Offer alternatives to the caller

### CRITICAL ANTI-PATTERNS (NEVER DO)

❌ Skip `get_current_datetime()` before time operations
❌ Guess event_id — always get it from `list_events()`
❌ Delete without explicit caller confirmation
❌ Use relative times in tool parameters ("tomorrow" is not ISO 8601)
❌ Mention tool names or internal processes to callers
❌ List ALL events to an unverified caller
"""

__all__ = ["calendar_guidelines_prompt"]
