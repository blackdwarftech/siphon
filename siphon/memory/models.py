"""Pydantic models for call memory using conversation summaries.

Defines the data structures for conversation summaries, caller memory, and extraction results.
Uses a simple text-based summary approach instead of structured facts.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class ConversationSummary(BaseModel):
    """A single conversation summary from one call."""
    
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="When the call occurred (UTC)")
    summary: str = Field(..., description="1-2 sentence summary of the conversation (max 150 chars)", max_length=150)
    call_number: int = Field(..., ge=1, description="Which call this was (1, 2, 3, etc.)")
    
    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class CallerMemory(BaseModel):
    """Complete memory profile for a caller using conversation summaries."""
    
    phone_number: str = Field(..., description="Normalized phone number as identifier")
    first_call_date: datetime = Field(default_factory=datetime.utcnow)
    last_call_date: datetime = Field(default_factory=datetime.utcnow)
    total_calls: int = Field(default=0, ge=0)
    summaries: List[ConversationSummary] = Field(default_factory=list)
    
    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
        extra = "ignore"


class SummaryResult(BaseModel):
    """Result of conversation summarization."""
    
    summary: str = Field(default="", description="Generated summary (1-2 sentences)")
    raw_response: Optional[str] = Field(default=None, description="Raw LLM response")
    success: bool = Field(default=False)
    error_message: Optional[str] = Field(default=None)


class MemoryContext(BaseModel):
    """Formatted memory ready for prompt injection."""
    
    has_history: bool = False
    total_calls: int = 0
    last_call_date: Optional[str] = None
    summaries_text: str = ""
    full_context: str = ""
