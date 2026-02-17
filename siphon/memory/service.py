"""Memory Service - orchestrates storage, summarization, and enrichment."""

from typing import Any, Dict, List, Optional
from datetime import datetime
from siphon.memory.models import CallerMemory, ConversationSummary, SummaryResult
from siphon.memory.storage import MemoryStore, create_memory_store
from siphon.memory.extraction.summarizer import ConversationSummarizer
from siphon.memory.enrichment import MemoryEnricher
from siphon.config import get_logger

logger = get_logger("calling-agent")


class MemoryService:
    """Main service for caller memory operations using conversation summaries.
    
    Orchestrates:
    - Storage (loading/saving memory)
    - Summarization (generating summaries from conversations)
    - Enrichment (formatting memory for prompts)
    """

    def __init__(
        self,
        phone_number: Optional[str] = None,
        store: Optional[MemoryStore] = None,
        enricher: Optional[MemoryEnricher] = None,
        enabled: bool = True,
    ) -> None:
        """Initialize memory service.
        
        Args:
            phone_number: Phone number for this memory context
            store: Storage backend (created automatically if not provided)
            enricher: Enricher for prompt formatting
            enabled: Whether memory operations are enabled
        """
        self._phone_number = phone_number
        self._enabled = enabled
        self._store = store or create_memory_store()
        self._enricher = enricher or MemoryEnricher()
        self._loaded_memory: Optional[CallerMemory] = None

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    @property
    def phone_number(self) -> Optional[str]:
        return self._phone_number

    def update_phone_number(self, phone_number: str) -> None:
        """Update the phone number for this service instance."""
        if phone_number and not self._phone_number:
            self._phone_number = phone_number
            logger.info(f"Memory service phone number updated: {phone_number}")

    async def load(self, phone_number: Optional[str] = None) -> Optional[CallerMemory]:
        """Load memory for a phone number.
        
        Args:
            phone_number: Phone number to load (uses stored if not provided)
            
        Returns:
            CallerMemory if found, None otherwise
        """
        if not self._enabled:
            return None

        phone = phone_number or self._phone_number
        if not phone:
            logger.debug("No phone number provided for memory load")
            return None

        try:
            memory = await self._store.get(phone)
            if memory:
                self._loaded_memory = memory
                logger.info(f"Loaded memory for {phone}: {memory.total_calls} calls, {len(memory.summaries)} summaries")
                return memory
            return None
        except Exception as e:
            logger.error(f"Error loading memory for {phone}: {e}")
            return None

    async def save(
        self,
        phone_number: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        llm: Optional[Any] = None,
    ) -> bool:
        """Save memory after a call.
        
        Generates summary from conversation and appends to existing memory.
        
        Args:
            phone_number: Phone number to save for
            conversation_history: Conversation messages to summarize
            llm: LLM for summarization
            
        Returns:
            True if saved successfully
        """
        if not self._enabled:
            logger.debug("Memory service not enabled, skipping save")
            return False

        phone = phone_number or self._phone_number
        if not phone:
            logger.warning("No phone number provided for memory save")
            return False

        try:
            # Load existing memory
            logger.debug(f"Loading existing memory for {phone}")
            existing = await self._store.get(phone)
            if not existing:
                logger.debug(f"No existing memory found for {phone}, creating new")
                existing = CallerMemory(phone_number=phone)
            else:
                logger.debug(f"Found existing memory with {existing.total_calls} calls and {len(existing.summaries)} summaries")

            # Generate summary for this call
            new_summary: Optional[ConversationSummary] = None
            if conversation_history and llm:
                new_summary = await self._generate_summary(
                    conversation_history, 
                    llm, 
                    existing.total_calls + 1
                )

            # Build updated memory
            now = datetime.utcnow()
            new_call_count = existing.total_calls + 1
            
            # Create new summary list
            updated_summaries = list(existing.summaries)
            if new_summary:
                updated_summaries.append(new_summary)

            memory = CallerMemory(
                phone_number=phone,
                first_call_date=existing.first_call_date,
                last_call_date=now,
                total_calls=new_call_count,
                summaries=updated_summaries,
            )

            # Save
            await self._store.save(phone, memory)
            logger.info(f"Saved memory for {phone}: {memory.total_calls} calls, {len(updated_summaries)} summaries")
            return True

        except Exception as e:
            logger.error(f"Error saving memory for {phone}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False

    def enhance_instructions(
        self,
        base_instructions: str,
        memory: Optional[CallerMemory] = None
    ) -> str:
        """Enhance instructions with memory context.
        
        Args:
            base_instructions: Original system instructions
            memory: Memory to use (loads if not provided)
            
        Returns:
            Enhanced instructions
        """
        mem = memory or self._loaded_memory
        return self._enricher.enhance_instructions(base_instructions, mem)

    def format_memory_for_prompt(self, memory: Optional[CallerMemory] = None) -> str:
        """Format memory as prompt text.
        
        Args:
            memory: Memory to format (uses loaded if not provided)
            
        Returns:
            Formatted memory string
        """
        mem = memory or self._loaded_memory
        context = self._enricher.format(mem)
        return context.full_context

    async def _generate_summary(
        self,
        conversation_history: List[Dict[str, Any]],
        llm: Any,
        call_number: int
    ) -> Optional[ConversationSummary]:
        """Generate summary from conversation using LLM."""
        try:
            summarizer = ConversationSummarizer(llm=llm)
            result = await summarizer.summarize(conversation_history)
            
            if result.success and result.summary:
                logger.info(f"Generated summary for call #{call_number}: {result.summary[:50]}...")
                return ConversationSummary(
                    timestamp=datetime.utcnow(),
                    summary=result.summary,
                    call_number=call_number
                )
            else:
                logger.warning(f"Summarization failed: {result.error_message}")
                return None
        except Exception as e:
            import traceback
            logger.error(f"Error generating summary: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None
