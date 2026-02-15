"""Memory enrichment - format memory for prompt injection."""

from typing import Optional
from datetime import datetime
from siphon.memory.models import CallerMemory, MemoryContext
from siphon.config import get_logger
from siphon.agent.internal_prompts import memory_aware_prompt

logger = get_logger("calling-agent")


class MemoryEnricher:
    """Formats caller memory for injection into system prompts."""

    def __init__(self, max_facts_in_prompt: int = 10) -> None:
        self.max_facts_in_prompt = max_facts_in_prompt

    def format(self, memory: Optional[CallerMemory]) -> MemoryContext:
        """Format memory into a context object ready for prompt injection."""
        if not memory:
            logger.debug("No memory provided, returning empty context")
            return MemoryContext()
        
        logger.debug(f"Formatting memory: call_count={memory.call_count}, facts={len(memory.facts)}")
        
        if memory.call_count < 1:
            logger.debug(f"call_count < 1 ({memory.call_count}), returning empty context")
            return MemoryContext()
        
        if not memory.facts:
            logger.debug("No facts in memory, returning empty context")
            return MemoryContext()
        
        logger.debug(f"Building context with {len(memory.facts)} facts")

        # Format last call date
        last_call_str = ""
        try:
            last_call_str = memory.last_call_date.strftime("%B %d, %Y")
        except:
            pass

        # Format facts
        facts_lines = []
        sorted_facts = sorted(memory.facts, key=lambda f: f.importance, reverse=True)
        
        for fact in sorted_facts[:self.max_facts_in_prompt]:
            key = fact.key.replace("_", " ").title()
            facts_lines.append(f"- {key}: {fact.value}")

        formatted_facts = "\n".join(facts_lines) if facts_lines else ""

        # Build full context
        lines = [
            "---",
            "Previous Conversation Context:",
        ]

        if memory.call_count > 1:
            if last_call_str:
                lines.append(f"This user has called {memory.call_count} times previously. Last call was on {last_call_str}.")
            else:
                lines.append(f"This user has called {memory.call_count} times previously.")

        if formatted_facts:
            lines.append("Key facts from previous conversations:")
            lines.append(formatted_facts)

        full_context = "\n".join(lines) if len(lines) > 2 else ""

        return MemoryContext(
            has_history=True,
            call_count=memory.call_count,
            last_call_date=last_call_str,
            formatted_facts=formatted_facts,
            full_context=full_context
        )

    def enhance_instructions(
        self,
        base_instructions: str,
        memory: Optional[CallerMemory]
    ) -> str:
        """Enhance base system instructions with memory context.
        
        Args:
            base_instructions: Original system instructions
            memory: Caller memory to inject
            
        Returns:
            Enhanced instructions with memory context and usage guidance
        """
        context = self.format(memory)
        if not context.full_context:
            return base_instructions
        
        # Combine: base instructions + how to use memory + the actual memory data
        enhanced = f"""{base_instructions}

                {memory_aware_prompt}

                {context.full_context}
                """
        
        return enhanced
