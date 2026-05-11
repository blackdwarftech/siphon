"""Memory Service - orchestrates storage, summarization, and enrichment."""

import asyncio
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from siphon.memory.models import CallerMemory, CallerProfile, ConversationSummary, SummaryResult
from siphon.memory.storage import MemoryStore, create_memory_store
from siphon.memory.extraction.summarizer import ConversationSummarizer
from siphon.memory.enrichment import MemoryEnricher
from siphon.config import get_logger, _redact_phone

logger = get_logger("calling-agent")


class MemoryService:
    """Main service for caller memory operations using conversation summaries.
    
    Orchestrates:
    - Storage (loading/saving memory)
    - Summarization (generating summaries from conversations)
    - Profile extraction (structured caller identity)
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
        self._locks: Dict[str, asyncio.Lock] = {}

    def _get_lock(self, phone: str) -> asyncio.Lock:
        if phone not in self._locks:
            self._locks[phone] = asyncio.Lock()
        return self._locks[phone]

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    @property
    def phone_number(self) -> Optional[str]:
        return self._phone_number

    def update_phone_number(self, phone_number: str) -> None:
        """Update the phone number for this service instance."""
        if phone_number and phone_number != self._phone_number:
            self._phone_number = phone_number
            logger.info(f"Memory service phone number updated: {_redact_phone(phone_number)}")

    async def load(self, phone_number: Optional[str] = None) -> Optional[CallerMemory]:
        """Load memory for a phone number.
        
        Loads memory from the database.
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
                logger.info(f"Loaded memory for {_redact_phone(phone)}: {memory.total_calls} calls, {len(memory.summaries)} summaries")
                return memory
            return None
        except Exception as e:
            logger.error(f"Error loading memory for {_redact_phone(phone)}: {e}")
            return None

    async def save(
        self,
        phone_number: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        llm: Optional[Any] = None,
    ) -> bool:
        """Save memory after a call.
        
        1. Generate summary from conversation
        2. Extract caller profile
        3. Save to database
        """
        if not self._enabled:
            logger.debug("Memory service not enabled, skipping save")
            return False

        phone = phone_number or self._phone_number
        if not phone:
            logger.warning("No phone number provided for memory save")
            return False

        try:
            # Step 1: Generate summary and profile (can fail independently)
            existing = await self._get_existing_memory(phone)
            new_summary, new_profile = await self._generate_summary_and_profile(
                conversation_history, llm, existing.total_calls + 1, phone
            )
            
            # Step 2: Only increment total_calls if summarization succeeded
            # This prevents the case where total_calls > len(summaries)
            call_number = existing.total_calls + 1
            if not new_summary:
                # Summary failed: don't increment counter, but still try to save
                # any profile updates
                call_number = existing.total_calls
                logger.warning(f"Summarization failed for call #{call_number}; not incrementing total_calls")
            
            memory = self._build_updated_memory(phone, existing, new_summary, new_profile, call_number)

            # Step 3: Save to store with per-phone locking to prevent races
            lock = self._get_lock(phone)
            async with lock:
                # Re-read existing memory inside the lock
                current_existing = await self._get_existing_memory(phone)
                
                # Merge with any concurrent changes
                if current_existing.total_calls > existing.total_calls:
                    logger.info(f"Concurrent memory update detected for {_redact_phone(phone)}, merging changes")
                    memory = self._merge_concurrent_updates(
                        current_existing, memory, new_summary, new_profile
                    )
                
                await self._store.save(phone, memory)
                logger.info(f"Saved memory for {_redact_phone(phone)}: {memory.total_calls} calls, {len(memory.summaries)} summaries, profile={memory.caller_profile}")
                return True

        except Exception as e:
            logger.error(f"Error saving memory for {_redact_phone(phone)}: {e}")
            logger.exception("Memory save traceback")
            return False

    async def _get_existing_memory(self, phone: str) -> CallerMemory:
        logger.debug(f"Loading existing memory for {_redact_phone(phone)}")
        existing = await self._store.get(phone)
        if not existing:
            logger.debug(f"No existing memory found for {_redact_phone(phone)}, creating new")
            return CallerMemory(phone_number=phone)
        logger.debug(f"Found existing memory with {existing.total_calls} calls and {len(existing.summaries)} summaries")
        return existing

    async def _generate_summary_and_profile(
        self,
        conversation_history: Optional[List[Dict[str, Any]]],
        llm: Optional[Any],
        call_number: int,
        phone: str
    ) -> tuple[Optional[ConversationSummary], Optional[CallerProfile]]:
        new_summary = None
        new_profile = None
        
        if conversation_history and llm:
            summarizer = ConversationSummarizer(llm=llm)
            new_summary = await self._generate_summary(
                summarizer, conversation_history, call_number
            )
            new_profile = await self._extract_profile(
                summarizer, conversation_history, phone
            )
        return new_summary, new_profile

    def _build_updated_memory(
        self,
        phone: str,
        existing: CallerMemory,
        new_summary: Optional[ConversationSummary],
        new_profile: Optional[CallerProfile],
        call_number: int = None
    ) -> CallerMemory:
        now = datetime.now(timezone.utc)
        new_call_count = call_number if call_number is not None else existing.total_calls + 1
        
        updated_summaries = list(existing.summaries)
        if new_summary:
            updated_summaries.append(new_summary)

        merged_profile = existing.caller_profile
        if new_profile:
            if merged_profile:
                merged_profile = merged_profile.merge(new_profile)
            else:
                merged_profile = new_profile
                
        if merged_profile:
            if not merged_profile.phone:
                merged_profile.phone = phone
        else:
            merged_profile = CallerProfile(phone=phone)

        return CallerMemory(
            phone_number=phone,
            first_call_date=existing.first_call_date,
            last_call_date=now if new_summary else existing.last_call_date,
            total_calls=new_call_count,
            summaries=updated_summaries,
            caller_profile=merged_profile,
        )
    
    def _merge_concurrent_updates(
        self,
        current: CallerMemory,
        proposed: CallerMemory,
        new_summary: Optional[ConversationSummary],
        new_profile: Optional[CallerProfile]
    ) -> CallerMemory:
        """Merge memory updates when concurrent saves are detected."""
        # Use the latest total_calls
        total_calls = max(current.total_calls, proposed.total_calls)
        
        # Merge summaries: deduplicate by (call_number, timestamp) instead of text content
        existing_summaries = {(s.call_number, s.timestamp): s for s in current.summaries}
        for s in proposed.summaries:
            key = (s.call_number, s.timestamp)
            if key not in existing_summaries:
                existing_summaries[key] = s
        
        # Merge profiles
        merged_profile = current.caller_profile
        if new_profile:
            if merged_profile:
                merged_profile = merged_profile.merge(new_profile)
            else:
                merged_profile = new_profile
        
        return CallerMemory(
            phone_number=current.phone_number,
            first_call_date=current.first_call_date,
            last_call_date=datetime.now(timezone.utc),
            total_calls=total_calls,
            summaries=list(existing_summaries.values()),
            caller_profile=merged_profile,
        )

    def enhance_instructions(
        self,
        base_instructions: str,
        memory: Optional[CallerMemory] = None
    ) -> str:
        """Enhance instructions with memory context."""
        mem = memory or self._loaded_memory
        return self._enricher.enhance_instructions(base_instructions, mem)

    def format_memory_for_prompt(self, memory: Optional[CallerMemory] = None) -> str:
        """Format memory as prompt text."""
        mem = memory or self._loaded_memory
        context = self._enricher.format(mem)
        return context.full_context

    async def _generate_summary(
        self,
        summarizer: ConversationSummarizer,
        conversation_history: List[Dict[str, Any]],
        call_number: int
    ) -> Optional[ConversationSummary]:
        """Generate summary from conversation using LLM."""
        try:
            result = await summarizer.summarize(conversation_history)
            
            if result.success and result.summary:
                logger.info(f"Generated summary for call #{call_number}: {result.summary[:80]}...")
                return ConversationSummary(
                    timestamp=datetime.now(timezone.utc),
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

    async def _extract_profile(
        self,
        summarizer: ConversationSummarizer,
        conversation_history: List[Dict[str, Any]],
        phone: str,
    ) -> Optional[CallerProfile]:
        """Extract caller profile from conversation."""
        try:
            result = await summarizer.extract_profile(conversation_history)
            if result.success and result.profile:
                # Ensure phone is always set
                if not result.profile.phone:
                    result.profile.phone = phone
                return result.profile
            return None
        except Exception as e:
            logger.error(f"Error extracting profile: {e}")
            return None
