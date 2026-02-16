"""Prompts for fact extraction from conversations."""

import json
from typing import Optional

from siphon.memory.extraction.schemas import get_extraction_schema_json


# System prompt for the LLM
SYSTEM_PROMPT = """You are a precise fact extraction assistant. Extract key facts from conversations using BRIEF context (25-40 characters). Be concise."""


# Base extraction prompt template
EXTRACTION_PROMPT_TEMPLATE = """Extract key facts from this phone conversation.

Conversation History:
{conversation_text}

EXTRACTION RULES:

1. ⚠️ CRITICAL: KEEP VALUES BRIEF WITH CONTEXT
   
   Target length: 25-40 characters per value (brief but informative)
   
   ✅ GOOD (Brief with context):
   - "user_name": "Sameer (introduced at start)" - 28 chars
   - "appointment_time": "1:45 AM (tentative)" - 24 chars
   - "next_action": "Will call back today" - 23 chars
   - "call_summary": "Brief intro, user will callback" - 33 chars
   
   ❌ BAD (Too verbose, wastes tokens):
   - "user_name": "Sameer (the caller introduced himself at the start of the conversation, indicating his identity)" - 90+ chars
   - "appointment_time": "Today at 2 a.m. (the scheduled appointment was mentioned as happening today at 2 a.m., which is important)" - 100+ chars

2. FACT CATEGORIES TO EXTRACT:
   - Personal info: name, contact (brief context)
   - Appointments: time, date, status (confirmed/tentative)
   - Next actions: callbacks, follow-ups needed
   - Call summary: 1-sentence overview

3. IMPORTANCE SCALE (1-10):
   - 10: Critical (name, confirmed appointments)
   - 7-9: Very important (tentative appointments, next actions)
   - 4-6: Useful (preferences, context)
   - 1-3: Skip

4. IMPORTANCE THRESHOLD: >= 4
5. Maximum 15 facts total
6. Use lowercase keys with underscores

REQUIRED OUTPUT FORMAT:
You MUST return valid JSON following this schema:

{json_schema}

EXAMPLE - Appointment Update Call:
{{
  "facts": [
    {{
      "key": "user_name",
      "value": "Sameer (introduced at start)",
      "importance": 10
    }},
    {{
      "key": "appointment_time",
      "value": "1:45 AM (tentative)",
      "importance": 9
    }},
    {{
      "key": "next_action",
      "value": "Will call back to confirm",
      "importance": 8
    }},
    {{
      "key": "call_summary",
      "value": "User changed appointment from 2:00 AM to 1:45 AM",
      "importance": 7
    }}
  ]
}}

EXAMPLE - Brief "Call Back" Call:
{{
  "facts": [
    {{
      "key": "user_name",
      "value": "Sameer (introduced briefly)",
      "importance": 10
    }},
    {{
      "key": "next_action",
      "value": "Will call back later today",
      "importance": 8
    }},
    {{
      "key": "call_summary",
      "value": "Brief intro, user will callback",
      "importance": 6
    }}
  ]
}}

CRITICAL INSTRUCTIONS:
- Return ONLY JSON, no markdown, no code blocks
- Keep values BRIEF: 25-40 characters with context
- NO long explanations - just the fact + brief context
- If user updates info (e.g., changes time), extract the NEW value
- If no important facts, return: {{"facts": []}}

Begin extraction now:"""


# Retry prompt for when parsing fails
RETRY_PROMPT_TEMPLATE = """Your previous response could not be parsed as valid JSON.

Parse Error: {error_message}

Extract facts again with BRIEF values (25-40 characters each).

Schema:
{json_schema}

IMPORTANT:
- Return ONLY valid JSON
- Keep values brief with context
- Example: "Sameer (introduced at start)" not long explanations
- If no facts: {{"facts": []}}

Conversation History:
{conversation_text}

Return valid JSON now:"""


# Strict prompt for final retry attempt
STRICT_RETRY_PROMPT_TEMPLATE = """FINAL ATTEMPT - Return valid JSON with brief values.

Schema:
{json_schema}

Example brief format:
{{
  "facts": [
    {{
      "key": "user_name",
      "value": "Name (brief context)",
      "importance": 10
    }},
    {{
      "key": "next_action",
      "value": "Will call back today",
      "importance": 8
    }}
  ]
}}

Conversation History:
{conversation_text}

Return JSON immediately:"""


def build_extraction_prompt(
    conversation_text: str,
    is_retry: bool = False,
    error_message: Optional[str] = None,
    is_final_attempt: bool = False
) -> str:
    """Build the extraction prompt with embedded JSON schema."""
    schema = get_extraction_schema_json()
    
    if is_final_attempt:
        return STRICT_RETRY_PROMPT_TEMPLATE.format(
            json_schema=schema,
            conversation_text=conversation_text
        )
    
    if is_retry and error_message:
        return RETRY_PROMPT_TEMPLATE.format(
            error_message=error_message,
            json_schema=schema,
            conversation_text=conversation_text
        )
    
    return EXTRACTION_PROMPT_TEMPLATE.format(
        json_schema=schema,
        conversation_text=conversation_text
    )


# Legacy prompts for backward compatibility
DEFAULT_EXTRACTION_PROMPT = EXTRACTION_PROMPT_TEMPLATE

__all__ = [
    'SYSTEM_PROMPT',
    'EXTRACTION_PROMPT_TEMPLATE',
    'RETRY_PROMPT_TEMPLATE',
    'STRICT_RETRY_PROMPT_TEMPLATE',
    'build_extraction_prompt',
    'DEFAULT_EXTRACTION_PROMPT',
]
