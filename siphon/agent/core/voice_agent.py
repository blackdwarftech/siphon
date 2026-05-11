import asyncio
import time
from datetime import datetime
from typing import AsyncIterable, Optional
from livekit.agents.voice import Agent, ModelSettings
from livekit import rtc
from livekit.agents import ChatContext
from siphon.config import get_logger, HangupCall, CallTranscription
from siphon.config.timezone_utils import get_timezone, get_timezone_name
from siphon.agent.internal_prompts import call_agent_prompt
import os

logger = get_logger("calling-agent")

from siphon.memory import MemoryService

# Maximum characters kept in the rolling agent-text buffer (for echo detection).
_AGENT_TEXT_BUFFER_MAX = 1000


def _get_current_datetime_stamp() -> str:
    """Generate a current date/time stamp for injection into the system prompt.
    
    This ensures the LLM always knows the real date/time without needing
    to call a tool (LLMs often skip tool calls and hallucinate dates).
    """
    tz = get_timezone()
    
    if tz is not None:
        now = datetime.now(tz)
        formatted = now.strftime("%A, %B %d, %Y at %I:%M %p %Z")
    else:
        now = datetime.now()
        formatted = now.strftime("%A, %B %d, %Y at %I:%M %p")
    
    return (
        f"\n**CURRENT DATE AND TIME: {formatted}**\n"
        f"Today is {now.strftime('%A')}. The year is {now.year}. "
        f"Use this as your reference for ALL date/time operations. "
        f"Do NOT guess or assume any other date.\n"
    )


class AgentSetup(Agent, HangupCall, CallTranscription):
    def __init__(self, 
        config: dict,
        send_greeting: bool,
        greeting_instructions: str,
        system_instructions: str, 
        interruptions_allowed: bool,
        room: rtc.Room = None,
        phone_number: Optional[str] = None,
        remember_call: bool = False,
        memory_service: Optional[MemoryService] = None,
    ) -> None:
        """Thin wrapper around LiveKit's voice Agent with greeting behavior.

        The config dict mirrors the job metadata and can be extended over time
        without changing the core AgentSession wiring.
        """
        hangup_flag = os.getenv("HANGUP_CALL", "true").strip().lower()
        recording_flag = os.getenv("CALL_RECORDING", "false").strip().lower()
        metadata_flag = os.getenv("SAVE_METADATA", "false").strip().lower()
        transcription_flag = os.getenv("SAVE_TRANSCRIPTION", "false").strip().lower()

        self.hangup_call = hangup_flag != "false"
        self.call_recording = recording_flag == "true"
        self.save_metadata = metadata_flag == "true"
        self.save_transcription = transcription_flag == "true"
        
        # Call memory settings
        self._call_memory_phone = phone_number
        self._call_memory_enabled = remember_call
        self._memory_service = memory_service

        # Initializing Config
        self.config = config
        self.send_greeting = send_greeting
        self.greeting_instructions = greeting_instructions
        
        # Build system instructions: base + datetime + core agent rules + calendar + memory
        memory_context = ""
        calendar_context = ""
        base_instructions = system_instructions
        
        # Extract memory context if present (added by MemoryService.enhance_instructions)
        if "## INTERNAL RULES - MEMORY-AWARE CONVERSATION" in system_instructions:
            parts = system_instructions.split("---\n## INTERNAL RULES - MEMORY-AWARE CONVERSATION")
            if len(parts) >= 2:
                base_instructions = parts[0].strip()
                memory_context = "---\n## INTERNAL RULES - MEMORY-AWARE CONVERSATION" + parts[1]
        
        # Extract calendar guidelines if present (added by entrypoint when google_calendar=True)
        if "## INTERNAL RULES - CALENDAR OPERATIONS" in base_instructions:
            parts = base_instructions.split("---\n## INTERNAL RULES - CALENDAR OPERATIONS")
            if len(parts) >= 2:
                base_instructions = parts[0].strip()
                calendar_context = "---\n## INTERNAL RULES - CALENDAR OPERATIONS" + parts[1]
        
        # Inject real current date/time directly into the prompt
        # This prevents the LLM from hallucinating dates from its training data
        datetime_stamp = _get_current_datetime_stamp()
        
        # Reconstruct: base + datetime + core rules + calendar + memory
        self.system_instructions = (
            base_instructions + 
            "\n\n" + datetime_stamp +
            "\n\n" + call_agent_prompt +
            ("\n\n" + calendar_context if calendar_context else "") +
            ("\n\n" + memory_context if memory_context else "")
        )
        
        self.interruptions_allowed = interruptions_allowed

        # Call Tracking
        self._greeting_sent = False 
        self.response = None

        # Initialize the ChatContext
        self.initial_ctx = ChatContext()

        Agent.__init__(
            self, 
            instructions=self.system_instructions, 
            chat_ctx=self.initial_ctx
        )

        HangupCall.__init__(
            self, 
            config=self.config,
            response=self.response,
            hangup_call=self.hangup_call, 
            call_recording=self.call_recording, 
            save_metadata=self.save_metadata
        )

        # Initialize transcription mixin for conversation tracking
        CallTranscription.__init__(self)

        # Rolling buffer of recent agent output text (for echo detection).
        # Filled by transcription_node() in real-time as LLM text streams to TTS.
        self._agent_text_buffer: str = ""

    async def _setup_recording_task(self):
        if self.call_recording:
            try:
                # Minimal delay for room stability
                await asyncio.sleep(0.5)  # Reduced from 1 second
                await self.start_recording()
                logger.info("Recording started...")
            except Exception as e:
                logger.error(f"Recording setup error: {e}") 

    async def _setup_monitoring_task(self):
        if self.save_transcription or self._call_memory_enabled:
            try:
                self.setup_conversation_monitoring(self.session)
                logger.info("Conversation monitoring setup")
            except Exception as e:
                logger.error(f"Monitoring setup error: {e}")

    async def _send_greeting_task(self):
        try:
            if self.send_greeting and not self._greeting_sent:
                greeting_instructions = self.greeting_instructions
                await self.session.generate_reply(
                    instructions=greeting_instructions,
                    allow_interruptions=self.interruptions_allowed
                )
                
                self._greeting_sent = True
                logger.info("Greeting sent")
        except Exception as e:
            logger.error(f"Greeting error: {e}", exc_info=True)

    # ------------------------------------------------------------------
    # Echo detection helpers
    # ------------------------------------------------------------------

    async def transcription_node(
        self, text: AsyncIterable, model_settings
    ) -> AsyncIterable:
        """Override to capture real-time LLM output for echo comparison.

        The transcription_node receives every text chunk the LLM produces
        (the same text that flows to TTS).  We accumulate it into a rolling
        buffer so the echo filter in entrypoint can compare incoming STT
        transcripts against what the agent is *currently* saying.
        """
        async for delta in text:
            self._agent_text_buffer += delta
            # Keep only the most-recent characters (tail)
            if len(self._agent_text_buffer) > _AGENT_TEXT_BUFFER_MAX:
                self._agent_text_buffer = self._agent_text_buffer[
                    -_AGENT_TEXT_BUFFER_MAX:
                ]
            yield delta

    def get_recent_agent_text(self, max_chars: int = 500) -> str:
        """Return the last *max_chars* characters the agent has generated."""
        if len(self._agent_text_buffer) <= max_chars:
            return self._agent_text_buffer
        return self._agent_text_buffer[-max_chars:]

    def clear_agent_text_buffer(self) -> None:
        """Clear the buffer (called when agent stops speaking)."""
        self._agent_text_buffer = ""

    # ------------------------------------------------------------------

    def update_phone_number(self, phone_number: Optional[str]) -> None:
        """Update memory phone number when SIP participant data becomes available."""
        if not phone_number:
            return

        if phone_number != self._call_memory_phone:
            self._call_memory_phone = phone_number

            if self._memory_service:
                self._memory_service.update_phone_number(phone_number)

            logger.info(f"Updated call memory phone number: {phone_number}")

    # Agent lifecycle
    async def on_enter(self):
        """Send an optional greeting when the agent joins the room."""
        # Mark the call start time for metadata tracking
        self.call_start_time = time.time()
        logger.info("Agent entering room...")

        await asyncio.gather(
            self._setup_recording_task(),
            self._setup_monitoring_task(),
            self._send_greeting_task(),
            return_exceptions=True
        )
    
    async def on_exit(self):
        # If this call was never actually answered, HangupCall.handle_unanswered_call
        # has already discarded any recording and saved a minimal metadata record.
        # In that case, we skip the normal on-exit persistence to avoid marking the
        # call as completed/answered or creating transcripts/recordings.
        if getattr(self, "_unanswered_call", False):
            logger.info("on_exit: unanswered call detected; skipping recording/metadata/transcription save")
            return

        # Stopping the call recording before ending the call
        if self.call_recording:
            try:
                self.response = await self.stop_recording()
                logger.info(f"Stopped recording before ending call. Response: {self.response}")
            except Exception as e:
                logger.error(f"Error stopping recording before ending call: {e}")
                self.response = None

        if self.save_metadata:
            await self.save_call_metadata(self.response)

        if self.save_transcription:
            await self._save_conversation()
        
        # Save call memory if enabled via MemoryService
        if self._call_memory_enabled and self._memory_service:
            try:
                # Access the session's LLM (not self.llm which may be NotGiven)
                session = getattr(self, 'session', None)
                session_llm = getattr(session, 'llm', None) if session else None
                self_llm = getattr(self, 'llm', None)
                config_llm = self.config.get("llm") if hasattr(self, 'config') else None
                actual_llm = session_llm or self_llm or config_llm
                
                await self._memory_service.save(
                    phone_number=self._call_memory_phone,
                    conversation_history=getattr(self, 'conversation_history', []),
                    llm=actual_llm
                )
            except Exception as e:
                logger.error(f"Error saving call memory: {e}")
