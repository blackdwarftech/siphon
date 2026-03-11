"""Memory enrichment - format conversation summaries for prompt injection."""

from typing import Optional
from datetime import datetime
from siphon.memory.models import CallerMemory, MemoryContext
from siphon.config import get_logger
from siphon.config.timezone_utils import get_timezone
from siphon.agent.internal_prompts import memory_aware_prompt

logger = get_logger("calling-agent")


DATE_FORMAT = "%b %d, %Y at %I:%M %p"


class MemoryEnricher:
    """Formats caller memory (conversation summaries) for injection into system prompts."""

    def __init__(self, max_summaries_in_prompt: int = 10) -> None:
        self.max_summaries_in_prompt = max_summaries_in_prompt

    def format(self, memory: Optional[CallerMemory]) -> MemoryContext:
        """Format memory into a context object ready for prompt injection."""
        if not self._is_valid_memory(memory):
            return MemoryContext()
            
        logger.debug(f"Building context with {len(memory.summaries)} summaries")

        last_call_str = self._format_last_call_date(memory)
        caller_identity = self._build_caller_identity(memory)
        summaries_text = self._build_summaries_text(memory)
        
        full_context = self._build_full_context(
            memory.total_calls, last_call_str, caller_identity, summaries_text
        )

        return MemoryContext(
            has_history=True,
            total_calls=memory.total_calls,
            last_call_date=last_call_str,
            caller_identity=caller_identity,
            summaries_text=summaries_text,
            full_context=full_context
        )

    def _is_valid_memory(self, memory: Optional[CallerMemory]) -> bool:
        if not memory:
            logger.debug("No memory provided, returning empty context")
            return False
        logger.debug(f"Formatting memory: total_calls={memory.total_calls}, summaries={len(memory.summaries)}")
        if memory.total_calls < 1:
            logger.debug(f"total_calls < 1 ({memory.total_calls}), returning empty context")
            return False
        if not memory.summaries:
            logger.debug("No summaries in memory, returning empty context")
            return False
        return True

    def _format_last_call_date(self, memory: CallerMemory) -> str:
        try:
            tz = get_timezone()
            if tz:
                last_call_dt = memory.last_call_date.astimezone(tz)
            else:
                last_call_dt = memory.last_call_date
            return last_call_dt.strftime(DATE_FORMAT)
        except Exception:
            return ""

    def _build_caller_identity(self, memory: CallerMemory) -> str:
        if not memory.caller_profile:
            return ""
            
        profile = memory.caller_profile
        identity_lines = []
        if profile.name:
            identity_lines.append(f"  Name: {profile.name}")
        if profile.phone:
            identity_lines.append(f"  Phone: {profile.phone}")
        if profile.email:
            identity_lines.append(f"  Email: {profile.email}")
        if profile.preferences:
            identity_lines.append(f"  Preferences: {profile.preferences}")
        
        if identity_lines:
            return "Caller Identity (from previous calls):\n" + "\n".join(identity_lines)
        return ""

    def _build_summaries_text(self, memory: CallerMemory) -> str:
        summaries_to_show = memory.summaries[-self.max_summaries_in_prompt:]
        tz = get_timezone()
        summary_lines = []
        
        for summary in summaries_to_show:
            try:
                if tz:
                    dt = summary.timestamp.astimezone(tz)
                else:
                    dt = summary.timestamp
                time_str = dt.strftime(DATE_FORMAT)
            except Exception:
                time_str = summary.timestamp.strftime(DATE_FORMAT)
            
            line = f"[{time_str}] Call #{summary.call_number} of {memory.total_calls}: {summary.summary}"
            summary_lines.append(line)

        return "\n".join(summary_lines) if summary_lines else ""

    def _build_full_context(self, total_calls: int, last_call_str: str, caller_identity: str, summaries_text: str) -> str:
        if not summaries_text:
            return ""
            
        lines = ["---"]
        if caller_identity:
            lines.append(caller_identity)
            lines.append("")

        lines.append(f"Previous Conversations (Total calls: {total_calls})")

        if last_call_str:
            lines.append(f"Last call was on {last_call_str}.")

        lines.append("")
        lines.append(summaries_text)
        return "\n".join(lines)

    def enhance_instructions(
        self,
        base_instructions: str,
        memory: Optional[CallerMemory]
    ) -> str:
        """Enhance base system instructions with memory context."""
        context = self.format(memory)
        if not context.full_context:
            logger.warning("Memory context is EMPTY - returning base instructions without memory")
            return base_instructions
        
        enhanced = f"""{base_instructions}

{memory_aware_prompt}

{context.full_context}
"""
        
        return enhanced
