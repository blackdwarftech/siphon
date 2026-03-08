"""Conversation summarization and caller profile extraction for memory storage.

This module provides reliable conversation summarization and identity extraction
using any LLM provider through LiveKit's unified interface.
"""

from typing import Any, Dict, List, Optional

from siphon.memory.models import SummaryResult, ProfileResult, CallerProfile
from siphon.config import get_logger

logger = get_logger("calling-agent")


SUMMARIZATION_PROMPT = """Summarize this phone conversation in 2-3 sentences (max 500 characters).

Include if mentioned:
- Caller's name
- What they wanted or asked about
- Key decisions made or actions taken
- Any next steps or outcomes

Example summaries:
- "Sameer (phone: +919876543210, email: sameer@gmail.com) called to schedule a dental cleaning appointment for March 5 at 2 PM. Appointment was confirmed."
- "Returning caller Priya asked about pricing for teeth whitening. She said she'd think about it and call back next week."
- "User called to reschedule their appointment from Tuesday 2 PM to Wednesday 3 PM. Change was confirmed."

Conversation:
{conversation_text}

Summary (2-3 sentences, max 500 chars):"""


PROFILE_EXTRACTION_PROMPT = """Extract the caller's identity from this conversation. Return ONLY the requested fields, one per line. If a field is not mentioned, write "UNKNOWN".

Format:
NAME: <caller's name or UNKNOWN>
EMAIL: <caller's email or UNKNOWN>
PREFERENCES: <any stated preferences or UNKNOWN>

Conversation:
{conversation_text}

Extract:"""


class ConversationSummarizer:
    """Summarize conversations and extract caller profiles.
    
    Works with ANY LLM provider and avoids JSON parsing issues.
    Returns text summaries and structured caller profiles.
    
    Args:
        llm: The LLM instance to use (any LiveKit-compatible LLM)
        max_length: Maximum character length for summaries (default: 500)
    """

    def __init__(
        self,
        llm: Any,
        max_length: int = 500,
    ) -> None:
        self.llm = llm
        self.max_length = max_length

    async def summarize(self, conversation_history: List[Dict[str, Any]]) -> SummaryResult:
        """Generate a summary of the conversation."""
        if not conversation_history:
            logger.warning("No conversation history provided for summarization")
            return SummaryResult(success=True)

        has_user_content = any(
            msg.get('role') == 'user' and msg.get('content', '').strip()
            for msg in conversation_history
        )
        
        if not has_user_content:
            logger.debug("No user responses found, skipping summarization")
            return SummaryResult(success=True)

        conversation_text = self._format_conversation(conversation_history)
        if not conversation_text.strip():
            logger.debug("Empty conversation text after formatting")
            return SummaryResult(success=True)

        try:
            prompt = SUMMARIZATION_PROMPT.format(conversation_text=conversation_text)
            
            logger.debug("Generating conversation summary")
            summary_text = await self._generate(prompt)
            
            if not summary_text:
                logger.warning("LLM returned empty summary")
                return SummaryResult(
                    success=False,
                    error_message="Empty summary from LLM"
                )

            if len(summary_text) > self.max_length:
                summary_text = summary_text[:self.max_length-3] + "..."
                logger.debug(f"Summary truncated to {self.max_length} characters")

            logger.info(f"Successfully generated summary: {summary_text[:80]}...")
            return SummaryResult(
                summary=summary_text,
                raw_response=summary_text,
                success=True
            )

        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return SummaryResult(
                success=False,
                error_message=str(e)
            )

    async def extract_profile(self, conversation_history: List[Dict[str, Any]]) -> ProfileResult:
        """Extract caller identity from conversation.
        
        Runs a targeted LLM call to pull out name, email, and preferences.
        Phone number is typically already known from the SIP participant.
        """
        if not conversation_history:
            return ProfileResult(success=True)

        has_user_content = any(
            msg.get('role') == 'user' and msg.get('content', '').strip()
            for msg in conversation_history
        )
        if not has_user_content:
            return ProfileResult(success=True)

        conversation_text = self._format_conversation(conversation_history)
        if not conversation_text.strip():
            return ProfileResult(success=True)

        try:
            prompt = PROFILE_EXTRACTION_PROMPT.format(conversation_text=conversation_text)
            raw = await self._generate(prompt)
            
            if not raw:
                return ProfileResult(success=True)

            profile = self._parse_profile(raw)
            if profile:
                logger.info(f"Extracted caller profile: name={profile.name}, email={profile.email}")
            return ProfileResult(profile=profile, success=True)

        except Exception as e:
            logger.error(f"Error extracting profile: {e}")
            return ProfileResult(success=False, error_message=str(e))

    def _parse_profile(self, raw: str) -> Optional[CallerProfile]:
        """Parse the structured profile extraction response."""
        name = None
        email = None
        preferences = None

        for line in raw.strip().split("\n"):
            line = line.strip()
            if line.upper().startswith("NAME:"):
                val = line.split(":", 1)[1].strip()
                if val and val.upper() != "UNKNOWN":
                    name = val
            elif line.upper().startswith("EMAIL:"):
                val = line.split(":", 1)[1].strip()
                if val and val.upper() != "UNKNOWN":
                    email = val
            elif line.upper().startswith("PREFERENCES:"):
                val = line.split(":", 1)[1].strip()
                if val and val.upper() != "UNKNOWN":
                    preferences = val

        if not any([name, email, preferences]):
            return None

        return CallerProfile(name=name, email=email, preferences=preferences)

    def _format_conversation(self, conversation_history: List[Dict[str, Any]]) -> str:
        """Format conversation history into readable text."""
        lines = []
        for msg in conversation_history:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            if content:
                role_display = role.capitalize()
                lines.append(f"{role_display}: {content}")
        return "\n".join(lines)

    async def _generate(self, prompt: str) -> Optional[str]:
        """Generate text using the configured LLM."""
        # Try LiveKit LLM first
        if hasattr(self.llm, 'chat') and callable(getattr(self.llm, 'chat')):
            try:
                return await self._generate_with_livekit(prompt)
            except Exception as e:
                logger.debug(f"LiveKit generation failed: {e}")
        
        # Try OpenAI-style interface as fallback
        if hasattr(self.llm, 'chat') and hasattr(self.llm.chat, 'completions'):
            try:
                return await self._generate_with_openai(prompt)
            except Exception as e:
                logger.debug(f"OpenAI generation failed: {e}")
        
        logger.error("No compatible LLM interface found")
        return None

    async def _generate_with_livekit(self, prompt: str) -> Optional[str]:
        """Generate using LiveKit LLM's unified chat interface."""
        try:
            from livekit.agents.llm import ChatMessage, ChatContext
            
            chat_ctx = ChatContext([
                ChatMessage(role="system", content=["You are a helpful assistant that extracts information from conversations briefly and accurately."]),
                ChatMessage(role="user", content=[prompt])
            ])
            
            chunks = []
            
            async with self.llm.chat(chat_ctx=chat_ctx) as stream:
                async for chunk in stream:
                    content = None
                    if hasattr(chunk, 'delta') and chunk.delta:
                        content = getattr(chunk.delta, 'content', None)
                    elif hasattr(chunk, 'content'):
                        content = chunk.content
                    
                    if content:
                        chunks.append(str(content))
            
            summary = "".join(chunks).strip()
            return summary if summary else None
            
        except Exception as e:
            logger.error(f"LiveKit generation error: {e}")
            raise

    async def _generate_with_openai(self, prompt: str) -> Optional[str]:
        """Generate using OpenAI-style completions API."""
        try:
            response = await self.llm.chat.completions.create(
                model=getattr(self.llm, 'model', 'gpt-4o-mini'),
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that extracts information from conversations briefly and accurately."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=200,
            )
            content = response.choices[0].message.content if response.choices else None
            return content.strip() if content else None
        except Exception as e:
            logger.error(f"OpenAI generation error: {e}")
            raise
