"""Memory enrichment - format conversation summaries for prompt injection."""

from typing import Optional
from datetime import datetime
from siphon.memory.models import CallerMemory, MemoryContext
from siphon.config import get_logger
from siphon.config.timezone_utils import get_timezone
from siphon.agent.internal_prompts import memory_aware_prompt

logger = get_logger("calling-agent")


class MemoryEnricher:
    """Formats caller memory (conversation summaries) for injection into system prompts."""

    def __init__(self, max_summaries_in_prompt: int = 10) -> None:
        self.max_summaries_in_prompt = max_summaries_in_prompt

    def format(self, memory: Optional[CallerMemory]) -> MemoryContext:
        """Format memory into a context object ready for prompt injection."""
        if not memory:
            logger.debug("No memory provided, returning empty context")
            return MemoryContext()
        
        logger.debug(f"Formatting memory: total_calls={memory.total_calls}, summaries={len(memory.summaries)}")
        
        if memory.total_calls < 1:
            logger.debug(f"total_calls < 1 ({memory.total_calls}), returning empty context")
            return MemoryContext()
        
        if not memory.summaries:
            logger.debug("No summaries in memory, returning empty context")
            return MemoryContext()
        
        logger.debug(f"Building context with {len(memory.summaries)} summaries")

        # Format last call date
        last_call_str = ""
        try:
            tz = get_timezone()
            if tz:
                last_call_dt = memory.last_call_date.astimezone(tz)
            else:
                last_call_dt = memory.last_call_date
            last_call_str = last_call_dt.strftime("%b %d, %Y at %I:%M %p")
        except:
            pass

        # Build caller identity section
        caller_identity = ""
        if memory.caller_profile:
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
                caller_identity = "Caller Identity (from previous calls):\n" + "\n".join(identity_lines)

        # Get summaries to display (last N calls)
        summaries_to_show = memory.summaries[-self.max_summaries_in_prompt:]
        
        # Build summaries text
        tz = get_timezone()
        summary_lines = []
        
        for summary in summaries_to_show:
            try:
                if tz:
                    dt = summary.timestamp.astimezone(tz)
                else:
                    dt = summary.timestamp
                time_str = dt.strftime("%b %d, %Y at %I:%M %p")
            except:
                time_str = summary.timestamp.strftime("%b %d, %Y at %I:%M %p")
            
            line = f"[{time_str}] Call #{summary.call_number} of {memory.total_calls}: {summary.summary}"
            summary_lines.append(line)

        summaries_text = "\n".join(summary_lines) if summary_lines else ""

        # Build full context
        lines = ["---"]

        if caller_identity:
            lines.append(caller_identity)
            lines.append("")

        lines.append(f"Previous Conversations (Total calls: {memory.total_calls})")

        if last_call_str:
            lines.append(f"Last call was on {last_call_str}.")

        if summaries_text:
            lines.append("")
            lines.append(summaries_text)

        full_context = "\n".join(lines) if summaries_text else ""

        return MemoryContext(
            has_history=True,
            total_calls=memory.total_calls,
            last_call_date=last_call_str,
            caller_identity=caller_identity,
            summaries_text=summaries_text,
            full_context=full_context
        )

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
