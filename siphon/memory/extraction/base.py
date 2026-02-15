"""Abstract base class for fact extractors."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List
from siphon.memory.models import ExtractionResult


class FactExtractor(ABC):
    """Abstract base class for extracting facts from conversation."""

    def __init__(self, min_importance: int = 6, max_facts: int = 15) -> None:
        self.min_importance = min_importance
        self.max_facts = max_facts

    @abstractmethod
    async def extract(self, conversation_history: List[Dict[str, Any]]) -> ExtractionResult:
        """Extract facts from conversation history.
        
        Args:
            conversation_history: List of conversation messages with role and content
            
        Returns:
            ExtractionResult with facts and metadata
        """
        pass

    def _format_conversation(self, conversation_history: List[Dict[str, Any]]) -> str:
        """Format conversation history for extraction prompt."""
        lines = []
        for msg in conversation_history:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if content:
                lines.append(f"{role.upper()}: {content}")
        return "\n".join(lines)
