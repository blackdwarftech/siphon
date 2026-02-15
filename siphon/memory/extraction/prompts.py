"""Prompts for fact extraction."""

DEFAULT_EXTRACTION_PROMPT = """Extract key facts from this phone conversation.

Conversation History:
{conversation_text}

Instructions:
1. Identify only important facts about the caller (name, appointments, preferences, issues, etc.)
2. Ignore small talk, greetings, and irrelevant details
3. Return a JSON array of facts with this structure:
   [
     {{"key": "user_name", "value": "extracted value", "importance": 9}},
     {{"key": "appointment_date", "value": "2026-02-20", "importance": 8}}
   ]

Important keys to look for:
- user_name (if caller states their name)
- appointment_date, appointment_time, appointment_type
- insurance_provider, insurance_plan
- reason_for_call, issue_description
- follow_up_needed
- preferences (language, communication method)
- previous_conversation_summary

Importance scale (1-10):
- 9-10: Critical (name, confirmed appointments, urgent issues)
- 6-8: Important (preferences, insurance, future appointments)
- 1-5: Nice to have (general context)

Only include facts with importance >= 6.
Maximum 15 facts total.

Return ONLY the JSON array, no other text."""

SYSTEM_PROMPT = "You extract structured facts from conversations accurately and concisely."
