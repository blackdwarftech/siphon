import asyncio
import time
from livekit.agents.voice import Agent
from livekit import rtc
from livekit.agents import ChatContext
from siphon.config import get_logger, HangupCall, CallTranscription
from siphon.agent.internal_prompts import call_agent_prompt, proactive_agent_prompt, datetime_awareness_prompt
import os

logger = get_logger("calling-agent")

from typing import Optional
from siphon.memory import MemoryService


class AgentSetup(Agent, HangupCall, CallTranscription):
    def __init__(self, 
        config: dict,
        send_greeting: bool,
        greeting_instructions: str,
        system_instructions: str, 
        interruptions_allowed: bool,
        room: rtc.Room = None,
        phone_number: str = None,
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
        
        # Combine user's system instructions with internal prompts:
        # 1. User's instructions (their agent's role/personality)
        # 2. Tool confidentiality rules (don't expose internal capabilities)
        # 3. Proactive behavior (task memory, acknowledgment handling, initiative)
        # 4. DateTime awareness (check current date/time before time-related operations)
        self.system_instructions = (
            system_instructions + 
            "\n\n" + call_agent_prompt + 
            "\n\n" + proactive_agent_prompt +
            "\n\n" + datetime_awareness_prompt
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

    # Agent lifecycle
    async def on_enter(self):
        """Send an optional greeting when the agent joins the room."""
        # Mark the call start time for metadata tracking
        self.call_start_time = time.time()
        logger.info("Agent entering room...")

        async def setup_recording():
            if self.call_recording:
                try:
                    # Minimal delay for room stability
                    await asyncio.sleep(0.5)  # Reduced from 1 second
                    await self.start_recording()
                    logger.info("Recording started...")
                except Exception as e:
                    logger.error(f"Recording setup error: {e}") 

        async def setup_conversation_monitoring():
            if self.save_transcription:
                try:
                    await self.setup_conversation_monitoring(self.session)
                    logger.info("Conversation monitoring setup")
                except Exception as e:
                    logger.error(f"Monitoring setup error: {e}")

        async def send_greeting():
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

        await asyncio.gather(
            setup_recording(),
            setup_conversation_monitoring(),
            send_greeting(),
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