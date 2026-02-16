"""Pydantic schemas for structured fact extraction from LLM outputs.

These models define the expected structure of LLM responses and provide
validation to ensure outputs conform to the schema.
"""

from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel, Field, field_validator


class ExtractedFact(BaseModel):
    """A single fact extracted from conversation.
    
    This model represents one fact with a key, value, and importance score.
    It validates that importance is within the valid range (1-10).
    """
    
    key: str = Field(
        ...,
        description="Fact identifier (e.g., 'user_name', 'appointment_date')",
        min_length=1,
        max_length=100
    )
    value: str = Field(
        ...,
        description="The extracted value",
        min_length=1,
        max_length=1000
    )
    importance: int = Field(
        ...,
        description="Importance score from 1 (low) to 10 (critical)",
        ge=1,
        le=10
    )
    
    @field_validator('key')
    @classmethod
    def validate_key_format(cls, v: str) -> str:
        """Ensure key uses valid format (lowercase, underscores)."""
        # Normalize to lowercase with underscores
        normalized = v.lower().strip().replace(' ', '_').replace('-', '_')
        return normalized


class FactExtractionOutput(BaseModel):
    """Structured output for fact extraction.
    
    This is the expected response format from the LLM. It contains a list
    of extracted facts with validation rules.
    """
    
    facts: List[ExtractedFact] = Field(
        default_factory=list,
        description="List of extracted facts from the conversation",
        max_length=15
    )
    
    @field_validator('facts')
    @classmethod
    def validate_facts_count(cls, v: List[ExtractedFact]) -> List[ExtractedFact]:
        """Ensure we don't exceed maximum number of facts."""
        if len(v) > 15:
            # Sort by importance and take top 15
            sorted_facts = sorted(v, key=lambda f: f.importance, reverse=True)
            return sorted_facts[:15]
        return v
    
    def to_memory_facts(self, source: str = "llm"):
        """Convert extracted facts to memory Fact models.
        
        Args:
            source: Source of extraction (default: "llm")
            
        Returns:
            List of Fact objects ready for storage
        """
        from siphon.memory.models import Fact
        
        now = datetime.utcnow()
        return [
            Fact(
                key=fact.key,
                value=fact.value,
                importance=fact.importance,
                extracted_at=now,
                source=source
            )
            for fact in self.facts
        ]


class ExtractionError(BaseModel):
    """Error information from failed extraction attempts."""
    
    error_type: str = Field(..., description="Type of error (parse, validation, etc.)")
    error_message: str = Field(..., description="Human-readable error message")
    raw_response: Optional[str] = Field(None, description="Raw LLM response that caused error")
    attempt_number: int = Field(1, description="Which retry attempt this error occurred on")


# JSON schema for embedding in prompts
EXTRACTION_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "facts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "Fact identifier (e.g., 'user_name', 'appointment_date')"
                    },
                    "value": {
                        "type": "string",
                        "description": "The extracted value"
                    },
                    "importance": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 10,
                        "description": "Importance score from 1 (low) to 10 (critical)"
                    }
                },
                "required": ["key", "value", "importance"]
            },
            "maxItems": 15,
            "description": "List of extracted facts"
        }
    },
    "required": ["facts"]
}


def get_extraction_schema_json() -> str:
    """Get the JSON schema as a formatted string for prompts.
    
    Returns:
        Formatted JSON schema string
    """
    import json
    return json.dumps(EXTRACTION_JSON_SCHEMA, indent=2)
