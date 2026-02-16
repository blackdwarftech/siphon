"""Pydantic models for call memory.

Defines the data structures for facts, caller memory, and extraction results.
"""

from datetime import datetime
from typing import Dict, List, Optional
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
    
    def merge_with_existing(self, existing_facts: List[Fact], max_facts: int = 50) -> List[Fact]:
        """Merge new facts with existing, keeping history with previous/current markers."""
        from datetime import datetime
        
        # Separate facts by whether they're being updated
        updated_keys = {f.key for f in self.facts}
        
        # Mark existing facts that are being updated as "previous"
        marked_existing = []
        for fact in existing_facts:
            if fact.key in updated_keys:
                # Mark as previous but keep it
                previous_value = fact.value
                # Check if it's already marked to avoid double-marking
                if "(CURRENT" not in previous_value and "(PREVIOUS" not in previous_value:
                    fact.value = f"{previous_value} (PREVIOUS - updated in latest call)"
            marked_existing.append(fact)
        
        # Mark new facts as "current"
        marked_new = []
        for fact in self.facts:
            # Check if it's already marked
            if "(CURRENT" not in fact.value and "(PREVIOUS" not in fact.value:
                fact.value = f"{fact.value} (CURRENT - most recent)"
            marked_new.append(fact)
        
        # Combine all facts
        all_facts = marked_existing + marked_new
        
        # Sort by extraction time (newest first), then by importance
        all_facts.sort(key=lambda f: (f.extracted_at, f.importance), reverse=True)
        
        # Limit to max_facts
        return all_facts[:max_facts]


class MemoryContext(BaseModel):
    """Formatted memory ready for prompt injection."""
    
    has_history: bool = False
    call_count: int = 0
    last_call_date: Optional[str] = None
    formatted_facts: str = ""
    full_context: str = ""
