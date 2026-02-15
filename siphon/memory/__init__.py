"""Siphon Memory Module - Caller memory management for voice agents.

This module provides a clean, production-ready architecture for managing
caller memory across conversations:

- **models**: Pydantic data models for facts and caller memory
- **storage**: Pluggable storage backends (local, S3, etc.)
- **extraction**: LLM-based fact extraction with strategy pattern
- **enrichment**: Format memory for prompt injection
- **service**: Main MemoryService orchestrator

Example Usage:
    from siphon.memory import MemoryService, create_memory_store
    
    # Create service
    service = MemoryService(phone_number="+1234567890")
    
    # Load memory at call start
    memory = await service.load()
    enhanced_instructions = service.enhance_instructions(base_prompt, memory)
    
    # Save memory at call end
    await service.save(
        conversation_history=messages,
        llm=agent_llm
    )
"""

from siphon.memory.models import Fact, CallerMemory, ExtractionResult, MemoryContext
from siphon.memory.storage import MemoryStore, LocalMemoryStore, create_memory_store
from siphon.memory.extraction import FactExtractor, LLMFactExtractor
from siphon.memory.enrichment import MemoryEnricher
from siphon.memory.service import MemoryService

__all__ = [
    # Models
    "Fact",
    "CallerMemory",
    "ExtractionResult",
    "MemoryContext",
    # Storage
    "MemoryStore",
    "LocalMemoryStore",
    "create_memory_store",
    # Extraction
    "FactExtractor",
    "LLMFactExtractor",
    # Enrichment
    "MemoryEnricher",
    # Service
    "MemoryService",
]
