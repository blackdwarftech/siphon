"""Simple conversation summarization for memory storage.

This module provides reliable conversation summarization using any LLM
provider through LiveKit's unified interface. Returns plain text summaries
instead of structured JSON for maximum compatibility.
"""

from typing import Any, Dict, List, Optional

from siphon.memory.models import SummaryResult
from siphon.config import get_logger

logger = get_logger("calling-agent")


# Simple summarization prompt - no JSON, just plain text
SUMMARIZATION_PROMPT = """Summarize this phone conversation in 1-2 sentences.

Instructions:
- Include who called (name if mentioned)
- What they wanted or asked about
- Any key decisions, changes, or next steps
- Maximum 150 characters

Example summaries:
- "User Sameer called to schedule a dental appointment for tomorrow at 2 PM. Appointment was confirmed."
- "User changed previous appointment from 2:00 AM to 1:45 AM. New time was noted as tentative."
- "First contact. User introduced himself as Sameer and requested information about teeth whitening services."

Conversation:
{conversation_text}

Summary (1-2 sentences, max 150 chars):"""


class ConversationSummarizer:
    """Summarize conversations using plain text generation.
    
    This approach works with ANY LLM provider and avoids JSON parsing issues.
    Returns a simple text summary that can be stored and displayed directly.
    
    Args:
        llm: The LLM instance to use for summarization (any LiveKit-compatible LLM)
        max_length: Maximum character length for summaries (default: 150)
    """

    def __init__(
        self,
        llm: Any,
        max_length: int = 150,
    ) -> None:
        self.llm = llm
        self.max_length = max_length

    async def summarize(self, conversation_history: List[Dict[str, Any]]) -> SummaryResult:
        """Generate a summary of the conversation.
        
        Args:
            conversation_history: List of conversation messages with 'role' and 'content'
            
        Returns:
            SummaryResult containing the generated summary
        """
        if not conversation_history:
            logger.warning("No conversation history provided for summarization")
            return SummaryResult(success=True)

        # Check if there's any user content
        has_user_content = any(
            msg.get('role') == 'user' and msg.get('content', '').strip()
            for msg in conversation_history
        )
        
        if not has_user_content:
            logger.debug("No user responses found, skipping summarization")
            return SummaryResult(success=True)

        # Format conversation
        conversation_text = self._format_conversation(conversation_history)
        if not conversation_text.strip():
            logger.debug("Empty conversation text after formatting")
            return SummaryResult(success=True)

        try:
            # Build prompt
            prompt = SUMMARIZATION_PROMPT.format(conversation_text=conversation_text)
            
            logger.debug("Generating conversation summary")
            
            # Generate summary
            summary_text = await self._generate_summary(prompt)
            
            if not summary_text:
                logger.warning("LLM returned empty summary")
                return SummaryResult(
                    success=False,
                    error_message="Empty summary from LLM"
                )

            # Truncate if too long
            if len(summary_text) > self.max_length:
                summary_text = summary_text[:self.max_length-3] + "..."
                logger.debug(f"Summary truncated to {self.max_length} characters")

            logger.info(f"Successfully generated summary: {summary_text[:50]}...")
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

    async def _generate_summary(self, prompt: str) -> Optional[str]:
        """Generate summary using the configured LLM."""
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
                ChatMessage(role="system", content=["You are a helpful assistant that summarizes conversations briefly."]),
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
                    {"role": "system", "content": "You are a helpful assistant that summarizes conversations briefly."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=100,  # Short response for summary
            )
            content = response.choices[0].message.content if response.choices else None
            return content.strip() if content else None
        except Exception as e:
            logger.error(f"OpenAI generation error: {e}")
            raise
