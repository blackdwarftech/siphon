"""Pydantic models for call memory using conversation summaries.

Defines the data structures for conversation summaries, caller memory, and extraction results.
Uses a text-based summary approach with optional structured caller identity.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class CallerProfile(BaseModel):
    """Caller identity learned across conversations.
    
    Generic — not tied to any specific integration.
    Fields are populated incrementally as the agent learns more about the caller.
    """
    name: Optional[str] = Field(default=None, description="Caller's name")
    phone: Optional[str] = Field(default=None, description="Caller's phone number")
    email: Optional[str] = Field(default=None, description="Caller's email address")
    preferences: Optional[str] = Field(default=None, description="Free-text preferences, e.g. 'prefers mornings'")

    def merge(self, other: "CallerProfile") -> "CallerProfile":
        """Merge another profile into this one. Newer non-None values take precedence."""
        return CallerProfile(
            name=other.name or self.name,
            phone=other.phone or self.phone,
            email=other.email or self.email,
            preferences=other.preferences or self.preferences,
        )


class ConversationSummary(BaseModel):
    """A single conversation summary from one call."""
    
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="When the call occurred (UTC)")
    summary: str = Field(..., description="2-3 sentence summary of the conversation (max 500 chars)", max_length=500)
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
    caller_profile: Optional[CallerProfile] = Field(default=None, description="Structured caller identity")
    
    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
        extra = "ignore"


class SummaryResult(BaseModel):
    """Result of conversation summarization."""
    
    summary: str = Field(default="", description="Generated summary (2-3 sentences)")
    raw_response: Optional[str] = Field(default=None, description="Raw LLM response")
    success: bool = Field(default=False)
    error_message: Optional[str] = Field(default=None)


class ProfileResult(BaseModel):
    """Result of caller profile extraction."""
    
    profile: Optional[CallerProfile] = None
    success: bool = Field(default=False)
    error_message: Optional[str] = Field(default=None)


class MemoryContext(BaseModel):
    """Formatted memory ready for prompt injection."""
    
    has_history: bool = False
    total_calls: int = 0
    last_call_date: Optional[str] = None
    caller_identity: str = ""
    summaries_text: str = ""
    full_context: str = ""
