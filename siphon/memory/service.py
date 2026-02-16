"""Memory Service - orchestrates storage, extraction, and enrichment."""

from typing import Any, Dict, List, Optional
from datetime import datetime
from siphon.memory.models import CallerMemory, Fact, ExtractionResult
from siphon.memory.storage import MemoryStore, create_memory_store
from siphon.memory.extraction import LLMFactExtractor
from siphon.memory.enrichment import MemoryEnricher
from siphon.config import get_logger

logger = get_logger("calling-agent")


class MemoryService:
    """Main service for caller memory operations.
    
    Orchestrates:
    - Storage (loading/saving memory)
    - Extraction (extracting facts from conversations)
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
                # Filter expired facts
                memory.facts = self._filter_expired_facts(memory.facts)
                self._loaded_memory = memory
                logger.info(f"Loaded memory for {phone}: {memory.call_count} calls, {len(memory.facts)} facts")
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
        
        Extracts facts from conversation and merges with existing memory.
        
        Args:
            phone_number: Phone number to save for
            conversation_history: Conversation messages to extract facts from
            llm: LLM for fact extraction
            
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
                logger.debug(f"Found existing memory with {existing.call_count} calls and {len(existing.facts)} facts")

            # Extract new facts
            new_facts: List[Fact] = []
            if conversation_history and llm:
                new_facts = await self._extract_facts(conversation_history, llm)

            # Merge facts
            merged_facts = self._merge_facts(existing.facts, new_facts)

            # Build updated memory
            now = datetime.utcnow()
            memory = CallerMemory(
                phone_number=phone,
                first_call_date=existing.first_call_date,
                last_call_date=now,
                call_count=existing.call_count + 1,
                facts=merged_facts,
            )

            # Save
            await self._store.save(phone, memory)
            logger.info(f"Saved memory for {phone}: {memory.call_count} calls, {len(merged_facts)} facts")
            return True

        except Exception as e:
            logger.error(f"Error saving memory for {phone}: {e}")
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

    async def _extract_facts(
        self,
        conversation_history: List[Dict[str, Any]],
        llm: Any
    ) -> List[Fact]:
        """Extract facts from conversation using LLM."""
        try:
            extractor = LLMFactExtractor(llm=llm)
            result = await extractor.extract(conversation_history)
            
            if result.success:
                logger.info(f"Extracted {len(result.facts)} facts from conversation")
                return result.facts
            else:
                logger.warning(f"Fact extraction failed: {result.error_message}")
                return []
        except Exception as e:
            import traceback
            logger.error(f"Error extracting facts: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return []

    def _merge_facts(self, existing: List[Fact], new: List[Fact]) -> List[Fact]:
        """Merge fact lists, keeping newest values for duplicate keys."""
        fact_map: Dict[str, Fact] = {}
        
        # Add existing first
        for fact in existing:
            fact_map[fact.key] = fact
        
        # Override with new
        for fact in new:
            fact_map[fact.key] = fact
        
        # Sort by importance and limit
        merged = sorted(fact_map.values(), key=lambda f: f.importance, reverse=True)
        return merged[:15]  # Max 15 facts

    def _filter_expired_facts(self, facts: List[Fact], ttl_days: int = 90) -> List[Fact]:
        """Remove facts older than TTL."""
        if ttl_days <= 0:
            return facts
        
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(days=ttl_days)
        
        filtered = []
        for fact in facts:
            if fact.extracted_at and fact.extracted_at >= cutoff:
                filtered.append(fact)
        
        return filtered
