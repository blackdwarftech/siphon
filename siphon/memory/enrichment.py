"""Memory enrichment - format memory for prompt injection."""

from typing import Optional, List, Dict
from datetime import datetime
from siphon.memory.models import CallerMemory, MemoryContext, Fact
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

        # Sort facts by importance
        sorted_facts = sorted(memory.facts, key=lambda f: f.importance, reverse=True)
        top_facts = sorted_facts[:self.max_facts_in_prompt]

        # Categorize facts for better organization
        summary_facts = [f for f in top_facts if f.key in ['call_summary', 'conversation_summary']]
        action_facts = [f for f in top_facts if f.key in ['next_action', 'follow_up_needed', 'incomplete_task']]
        personal_facts = [f for f in top_facts if f.key in ['user_name', 'contact_number', 'email']]
        appointment_facts = [f for f in top_facts if 'appointment' in f.key or 'schedule' in f.key]
        other_facts = [f for f in top_facts if f.key not in 
                      ['call_summary', 'conversation_summary', 'next_action', 'follow_up_needed', 
                       'incomplete_task', 'user_name', 'contact_number', 'email'] and
                      'appointment' not in f.key and 'schedule' not in f.key]

        # Build sections
        sections = []
        
        # Header section
        sections.append("---")
        sections.append("Previous Conversation Context:")
        sections.append("")
        
        if memory.call_count > 1:
            if last_call_str:
                sections.append(f"This user has called {memory.call_count} times previously. Last call was on {last_call_str}.")
            else:
                sections.append(f"This user has called {memory.call_count} times previously.")
            sections.append("")

        # Summary section (most important for context)
        if summary_facts:
            sections.append("SUMMARY:")
            for fact in summary_facts[:2]:  # Max 2 summaries
                sections.append(f"  {fact.value}")
            sections.append("")

        # Next Actions section (critical for follow-ups)
        if action_facts:
            sections.append("NEXT ACTIONS / FOLLOW-UPS:")
            for fact in action_facts[:3]:  # Max 3 actions
                key_display = fact.key.replace("_", " ").title()
                sections.append(f"  • {key_display}: {fact.value}")
            sections.append("")

        # Personal Information section
        if personal_facts:
            sections.append("PERSONAL INFO:")
            for fact in personal_facts[:3]:
                key_display = fact.key.replace("_", " ").title()
                sections.append(f"  • {key_display}: {fact.value}")
            sections.append("")

        # Appointments section
        if appointment_facts:
            sections.append("APPOINTMENTS:")
            for fact in appointment_facts[:3]:
                key_display = fact.key.replace("_", " ").title()
                sections.append(f"  • {key_display}: {fact.value}")
            sections.append("")

        # Other important facts
        if other_facts:
            sections.append("OTHER KEY DETAILS:")
            for fact in other_facts[:5]:  # Max 5 other facts
                key_display = fact.key.replace("_", " ").title()
                # Truncate long values for readability
                value = fact.value
                if len(value) > 100:
                    value = value[:97] + "..."
                sections.append(f"  • {key_display}: {value}")
            sections.append("")

        # Join all sections
        full_context = "\n".join(sections)
        
        # Also create simple formatted_facts for backward compatibility
        formatted_facts_lines = []
        for fact in top_facts[:self.max_facts_in_prompt]:
            key_display = fact.key.replace("_", " ").title()
            formatted_facts_lines.append(f"- {key_display}: {fact.value}")
        formatted_facts = "\n".join(formatted_facts_lines)

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
