"""Siphon Memory Module - Caller memory management for voice agents.

This module provides a clean, production-ready architecture for managing
caller memory across conversations using simple conversation summaries:

- **models**: Pydantic data models for conversation summaries and caller memory
- **storage**: Pluggable storage backends (local, S3, PostgreSQL, MySQL, etc.)
- **extraction**: LLM-based conversation summarization
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

from siphon.memory.models import (
    ConversationSummary,
    CallerMemory, 
    SummaryResult, 
    MemoryContext
)
from siphon.memory.storage import MemoryStore, LocalMemoryStore, create_memory_store
from siphon.memory.extraction.summarizer import ConversationSummarizer
from siphon.memory.enrichment import MemoryEnricher
from siphon.memory.service import MemoryService

__all__ = [
    # Models
    "ConversationSummary",
    "CallerMemory",
    "SummaryResult",
    "MemoryContext",
    # Storage
    "MemoryStore",
    "LocalMemoryStore",
    "create_memory_store",
    # Extraction
    "ConversationSummarizer",
    # Enrichment
    "MemoryEnricher",
    # Service
    "MemoryService",
]
