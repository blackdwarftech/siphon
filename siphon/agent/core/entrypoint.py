from livekit.agents import JobContext, room_io
from livekit import rtc
from livekit.agents.voice import AgentSession
from livekit.plugins import silero, noise_cancellation
from .voice_agent import AgentSetup
import json
import asyncio
from typing import Any, Optional, Dict, List, Tuple
from siphon.agent.agent_components.llm import get_llm_component
from siphon.agent.agent_components.stt import get_stt_component
from siphon.agent.agent_components.tts import get_tts_component
from .utils import resolve_component
from siphon.config import get_logger

logger = get_logger("calling-agent")


async def monitor_call(ctx: JobContext, agent: AgentSetup):
    logger.info("Starting SIP call status monitoring...")

    monitoring_span = None
    timeout_seconds = 30
    start_time = asyncio.get_event_loop().time()

    try:
        while True:
            current_time = asyncio.get_event_loop().time()
            if (current_time - start_time) > timeout_seconds:
                await agent.handle_unanswered_call()
                return False
            
            sip_status_result = _check_sip_status(ctx, agent)
            if sip_status_result is not None:
                if sip_status_result is False:
                    await agent.handle_unanswered_call()
                return sip_status_result

            await asyncio.sleep(0.1)  
    finally:
        if monitoring_span:
            monitoring_span.end()


def _check_sip_status(ctx: JobContext, agent: AgentSetup) -> Optional[bool]:
    if not ctx.room.remote_participants:
        return None
        
    for participant in ctx.room.remote_participants.values():
        sip_status = participant.attributes.get("sip.callStatus")

        if sip_status == "active":
            _handle_active_sip(participant, agent)
            return True
        elif sip_status == "hangup":
            return False
            
    return None


def _handle_active_sip(participant, agent: AgentSetup) -> None:
    attrs = getattr(participant, "attributes", {}) or {}
    caller_number = attrs.get("sip.phoneNumber") or participant.identity

    if hasattr(agent, 'update_inbound_phone_numbers'):
        agent.update_inbound_phone_numbers(caller_number)
    
    if hasattr(agent, 'update_phone_number') and caller_number:
        agent.update_phone_number(caller_number)
        logger.info(f"Updated call memory phone number from SIP: {caller_number}")


def _load_metadata(ctx: JobContext) -> Optional[Dict[str, Any]]:
    """Load and parse job metadata from the context.

    Returns a dict on success or None when metadata is missing/invalid.
    """
    raw_metadata = ctx.job.metadata or "{}"
    try:
        return json.loads(raw_metadata)
    except json.JSONDecodeError:
        logger.error("Invalid job metadata JSON: %s", raw_metadata)
        return None


def _derive_agent_config(
    metadata: Dict[str, Any],
    llm: Optional[Dict[str, Any]],
    stt: Optional[Dict[str, Any]],
    tts: Optional[Dict[str, Any]],
    greeting_instructions: str,
    system_instructions: str,
) -> Tuple[bool, Dict[str, Any], Any, Any, Any, str, str]:
    """Derive agent configuration from metadata and optional defaults.

    Returns:
        is_inbound_call, agent_config, llm, stt, tts,
        greeting_instructions, system_instructions
    """
    # Outbound calls wrap agent configuration under the "agent_config" key.
    # Inbound calls usually provide metadata at the top level instead.
    if "agent_config" in metadata:
        is_inbound_call = False
        agent_config = metadata.get("agent_config", {})

        if agent_config.get("llm"):
            llm_cfg = agent_config.get("llm")
            llm = get_llm_component(llm_cfg)

        if agent_config.get("tts"):
            tts_cfg = agent_config.get("tts")
            tts = get_tts_component(tts_cfg)

        if agent_config.get("stt"):
            stt_cfg = agent_config.get("stt")
            stt = get_stt_component(stt_cfg)

        if agent_config.get("greeting_instructions"):
            greeting_instructions = agent_config.get(
                "greeting_instructions", greeting_instructions
            )

        if agent_config.get("system_instructions"):
            system_instructions = agent_config.get(
                "system_instructions", system_instructions
            )
    else:
        is_inbound_call = True
        agent_config = metadata
        logger.info("Detected inbound call based on missing agent_config key")

    logger.info(
        "Call type detected: %s",
        "inbound" if is_inbound_call else "outbound",
    )

    return (
        is_inbound_call,
        agent_config,
        llm,
        stt,
        tts,
        greeting_instructions,
        system_instructions,
    )


def _build_agent_class(tools: Optional[List[Any]], google_calendar: bool = False, date_time: bool = True) -> type:
    """Compose AgentSetup with any user-provided tool mixins and optional integrations.
    
    Args:
        tools: User-provided tool classes/mixins
        google_calendar: Whether to include GoogleCalendar integration
        date_time: Whether to include DateTime integration
    
    Returns:
        Dynamically constructed agent class with appropriate mixins
    """
    # Start with base AgentSetup
    base_classes = [AgentSetup]
    
    # Add DateTime mixin if enabled
    if date_time:
        from siphon.integrations import DateTime
        base_classes.append(DateTime)
    
    # Conditionally add GoogleCalendar
    if google_calendar:
        from siphon.integrations import GoogleCalendar
        base_classes.append(GoogleCalendar)
    
    # Note: CallMemory mixin removed. Memory is now handled via MemoryService composition
    # in entrypoint, not class inheritance. This provides cleaner separation of concerns.
    
    # Add user tool classes
    user_tool_classes = tools or []
    if not isinstance(user_tool_classes, (list, tuple)):
        user_tool_classes = [user_tool_classes]
    
    base_classes.extend(user_tool_classes)
    
    # If we only have AgentSetup, return it directly
    if len(base_classes) == 1:
        return AgentSetup
    
    # Otherwise, create a new class with all mixins
    agent_cls = type(
        "UserAgentSetup",
        tuple(base_classes),
        {},
    )
    return agent_cls


def _resolve_session_components(llm: Any, stt: Any, tts: Any) -> Tuple[Any, Any, Any]:
    """Unwrap any plugin wrappers to get underlying LiveKit-compatible clients."""
    session_llm = resolve_component(llm)
    session_tts = resolve_component(tts)
    session_stt = resolve_component(stt)
    return session_llm, session_stt, session_tts


def _build_agent_session(
    session_llm: Any,
    session_stt: Any,
    session_tts: Any,
    allow_interruptions: bool,
    min_silence_duration: float,
    activation_threshold: float,
    prefix_padding_duration: float,
    min_endpointing_delay: float,
    max_endpointing_delay: float,
    min_interruption_duration: float,
) -> AgentSession:
    """Construct an AgentSession with the configured models and settings."""
    vad_instance = silero.VAD.load(
        min_silence_duration=min_silence_duration,
        activation_threshold=activation_threshold,
        prefix_padding_duration=prefix_padding_duration,
    )

    return AgentSession(
        llm=session_llm,
        tts=session_tts,
        stt=session_stt,
        vad=vad_instance,
        turn_detection="stt",
        allow_interruptions=allow_interruptions,
        min_endpointing_delay=min_endpointing_delay,
        max_endpointing_delay=max_endpointing_delay,
        min_interruption_duration=min_interruption_duration,
        max_tool_steps=1000,
    )


async def _setup_memory_and_agent(
    agent_cls,
    metadata,
    is_inbound_call,
    remember_call,
    system_instructions,
    google_calendar,
    date_time,
    send_greeting,
    greeting_instructions,
    allow_interruptions,
    room,
):
    # Extract phone number from metadata for call memory
    phone_number = None
    if remember_call:
        # Try to get phone number from metadata
        if is_inbound_call:
            # For inbound, we'll get it from SIP participant later
            phone_number = metadata.get("user_number")
        else:
            # For outbound, it's the number we called
            phone_number = metadata.get("number_to_call") or metadata.get("user_number")
        
        logger.info(f"Call memory enabled. Phone number from metadata: {phone_number}")

    # Initialize MemoryService for call memory
    memory_service = None
    enhanced_instructions = system_instructions
    if remember_call:
        from siphon.memory import MemoryService
        memory_service = MemoryService(
            phone_number=phone_number,
            enabled=remember_call
        )
        
        if phone_number:
            loaded_memory = await memory_service.load(phone_number)
            if loaded_memory:
                logger.info(f"Loaded memory for {phone_number}: total_calls={loaded_memory.total_calls}, summaries={len(loaded_memory.summaries)}")
                enhanced_instructions = memory_service.enhance_instructions(
                    system_instructions, loaded_memory
                )
            else:
                logger.info(f"No previous call memory found for {phone_number}")
    
    # Inject calendar operation guidelines if Google Calendar integration is enabled
    if google_calendar:
        from siphon.agent.internal_prompts import calendar_guidelines_prompt
        enhanced_instructions = enhanced_instructions + "\n\n" + calendar_guidelines_prompt
        logger.info("Injected calendar operation guidelines into system instructions")
    
    agent_setup = agent_cls(
        config=metadata,
        send_greeting=send_greeting,
        greeting_instructions=greeting_instructions,
        system_instructions=enhanced_instructions,
        interruptions_allowed=allow_interruptions,
        room=room,
        phone_number=phone_number,
        remember_call=remember_call,
        memory_service=memory_service,
    )
    
    # Initialize DateTime if it's in the class hierarchy and enabled
    if date_time and hasattr(agent_setup, '__class__'):
        from siphon.integrations import DateTime
        if DateTime in agent_setup.__class__.__mro__:
            DateTime.__init__(agent_setup)
    
    # Initialize GoogleCalendar if it's in the class hierarchy
    if google_calendar and hasattr(agent_setup, '__class__'):
        from siphon.integrations import GoogleCalendar
        if GoogleCalendar in agent_setup.__class__.__mro__:
            GoogleCalendar.__init__(agent_setup)

    return agent_setup, memory_service


async def entrypoint(
    ctx: JobContext, 
    llm: Optional[Dict[str, Any]] = None,
    stt: Optional[Dict[str, Any]] = None,
    tts: Optional[Dict[str, Any]] = None,
    **kwargs: Any
): 
    """LiveKit worker entrypoint for voice agents.

    This function is invoked by LiveKit Agents for each job. It inspects the
    job metadata to determine whether the call is inbound or outbound,
    reconstructs the LLM/STT/TTS components from config, and starts an
    AgentSession bound to the current room.
    """
    send_greeting = kwargs.get("send_greeting", True)
    greeting_instructions = kwargs.get("greeting_instructions", "Greet and introduce yourself briefly")
    system_instructions = kwargs.get("system_instructions", "You are a helpful voice assistant")
    allow_interruptions = kwargs.get("allow_interruptions", True)
    min_silence_duration = kwargs.get("min_silence_duration", 0.25)
    activation_threshold = kwargs.get("activation_threshold", 0.25)
    prefix_padding_duration = kwargs.get("prefix_padding_duration", 1.0)
    min_endpointing_delay = kwargs.get("min_endpointing_delay", 0.25)
    max_endpointing_delay = kwargs.get("max_endpointing_delay", 1.5)
    min_interruption_duration = kwargs.get("min_interruption_duration", 0.05)
    tools = kwargs.get("tools", None)
    google_calendar = kwargs.get("google_calendar", False)
    date_time = kwargs.get("date_time", True)
    remember_call = kwargs.get("remember_call", False)

    agent_setup: Optional[AgentSetup] = None
    try:
        metadata = _load_metadata(ctx)
        if metadata is None:
            return

        (
            is_inbound_call,
            agent_config,
            llm,
            stt,
            tts,
            greeting_instructions,
            system_instructions,
        ) = _derive_agent_config(
            metadata,
            llm,
            stt,
            tts,
            greeting_instructions,
            system_instructions,
        )

        agent_cls = _build_agent_class(tools, google_calendar=google_calendar, date_time=date_time)

        agent_setup, _ = await _setup_memory_and_agent(
            agent_cls,
            metadata,
            is_inbound_call,
            remember_call,
            system_instructions,
            google_calendar,
            date_time,
            send_greeting,
            greeting_instructions,
            allow_interruptions,
            ctx.room,
        )

        logger.info("Entrypoint LLM object: %s, Type: %s", llm, type(llm))
        session_llm, session_stt, session_tts = _resolve_session_components(
            llm,
            stt,
            tts,
        )

        logger.info(
            "Session components - LLM: %s, TTS: %s, STT: %s, "
            "Greeting Instruction: %s, System Instruction: %s, Tools: %s",
            session_llm,
            session_tts,
            session_stt,
            greeting_instructions,
            system_instructions,
            tools,
        )

        session = _build_agent_session(
            session_llm=session_llm,
            session_stt=session_stt,
            session_tts=session_tts,
            allow_interruptions=allow_interruptions,
            min_silence_duration=min_silence_duration,
            activation_threshold=activation_threshold,
            prefix_padding_duration=prefix_padding_duration,
            min_endpointing_delay=min_endpointing_delay,
            max_endpointing_delay=max_endpointing_delay,
            min_interruption_duration=min_interruption_duration,
        )

        await session.start(
            room=ctx.room,
            agent=agent_setup,
            room_options=room_io.RoomOptions(
                audio_input=room_io.AudioInputOptions(
                    noise_cancellation=lambda params: noise_cancellation.BVCTelephony() 
                    if params.participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP 
                    else noise_cancellation.BVC(),
                ),
            ),
        )
        logger.info("Agent session started successfully.")

        call_result = await monitor_call(ctx, agent_setup)
        logger.info("Call result: %s", call_result)

    except Exception:
        logger.exception("Error in entrypoint")

        if agent_setup:
            try:
                await agent_setup.handle_unanswered_call()
            except Exception as meta_error:
                logger.error(
                    "Error saving metadata for failed call: %s", meta_error
                )
