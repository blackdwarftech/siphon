"""Pydantic models for call memory.

Defines the data structures for facts, caller memory, and extraction results.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class Fact(BaseModel):
    """A single extracted fact about a caller."""
    
    key: str = Field(..., description="Fact identifier (e.g., 'user_name', 'appointment_date')")
    value: str = Field(..., description="The extracted value")
    importance: int = Field(default=5, ge=1, le=10, description="Importance score 1-10")
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    source: Optional[str] = Field(default=None, description="Source of extraction (e.g., 'llm', 'manual')")
    
    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class CallerMemory(BaseModel):
    """Complete memory profile for a caller."""
    
    phone_number: str = Field(..., description="Normalized phone number as identifier")
    first_call_date: datetime = Field(default_factory=datetime.utcnow)
    last_call_date: datetime = Field(default_factory=datetime.utcnow)
    call_count: int = Field(default=0, ge=0)
    facts: List[Fact] = Field(default_factory=list)
    
    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
        extra = "ignore"  # Ignore extra fields like 'metadata'


class ExtractionResult(BaseModel):
    """Result of fact extraction from conversation."""
    
    facts: List[Fact] = Field(default_factory=list)
    raw_response: Optional[str] = Field(default=None, description="Raw LLM response")
    success: bool = Field(default=False)
    error_message: Optional[str] = Field(default=None)
    
    def merge_with_existing(self, existing_facts: List[Fact], max_facts: int = 15) -> List[Fact]:
        """Merge new facts with existing, keeping most recent values for duplicate keys."""
        fact_map: Dict[str, Fact] = {}
        
        # Add existing facts first
        for fact in existing_facts:
            fact_map[fact.key] = fact
        
        # Override with new facts (newer wins)
        if memory and memory.call_count < 1:
            return []
        for fact in self.facts:
            fact_map[fact.key] = fact
        
        # Sort by importance and limit
        merged = sorted(fact_map.values(), key=lambda f: f.importance, reverse=True)
        return merged[:max_facts]


class MemoryContext(BaseModel):
    """Formatted memory ready for prompt injection."""
    
    has_history: bool = False
    call_count: int = 0
    last_call_date: Optional[str] = None
    formatted_facts: str = ""
    full_context: str = ""
