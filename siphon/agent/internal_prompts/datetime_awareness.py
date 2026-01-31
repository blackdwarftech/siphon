datetime_awareness_prompt = """
---
## INTERNAL RULE - DATE/TIME AWARENESS
---

**CRITICAL: Check Current Date/Time Before Time-Related Operations**

**When Required:**
- Before creating/searching/updating appointments or events
- Before any operation involving "today", "tomorrow", "next week", etc.
- First time-related tool call in conversation

**How:**
1. **Call `get_current_datetime()` FIRST** (before list_events, create_event, etc.)
2. Use result to know what "today", "tomorrow" mean
3. Convert relative terms → ISO 8601 dates with timezone

**Example:**
```
User: "Book me for tomorrow at 2 PM"

Tool Sequence:
1. get_current_datetime() → "Thursday, Jan 30, 2026 at 11:00 AM IST"
2. list_events(timeMin="2026-01-31T14:00:00+05:30") → Check availability
3. create_event(..., start="2026-01-31T14:00:00+05:30") → Book
```

**Re-checking:**
- Can check again during long conversations
- NOT required for every single tool call
- Only re-check if temporal context unclear

**DO:**
✅ Call get_current_datetime() before first time operation
✅ Convert "tomorrow" → actual ISO date
✅ Include timezone in all timestamps

**DON'T:**
❌ Skip datetime check and guess the date
❌ Use "tomorrow" in tool parameters
❌ Check redundantly on every tool call

"""

