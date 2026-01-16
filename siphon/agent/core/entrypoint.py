from livekit.agents import JobContext
from livekit.agents.voice import AgentSession
from livekit.plugins import silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel
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

    # Wait for SIP participant to join or timeout
    timeout_seconds = 30
    start_time = asyncio.get_event_loop().time()

    try:
        while True:
            current_time = asyncio.get_event_loop().time()
            elapsed = current_time - start_time

            # Check if timeout reached
            if elapsed > timeout_seconds:
                await agent.handle_unanswered_call()
                return False
            
            # Check for SIP participants
            if ctx.room.remote_participants:
                for participant in ctx.room.remote_participants.values():
                    sip_status = participant.attributes.get("sip.callStatus")

                    if sip_status == "active":
                        # Update inbound numbers when we first see an active SIP participant
                        attrs = getattr(participant, "attributes", {}) or {}
                        caller_number = attrs.get("sip.phoneNumber") or participant.identity

                        if hasattr(agent, 'update_inbound_phone_numbers'):
                            agent.update_inbound_phone_numbers(caller_number)

                        return True
                    elif sip_status == "hangup":
                        await agent.handle_unanswered_call()
                        return False

            await asyncio.sleep(0.1)  
    finally:
        if monitoring_span:
            monitoring_span.end()


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


async def _derive_agent_config(
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
            llm = await get_llm_component(llm_cfg)

        if agent_config.get("tts"):
            tts_cfg = agent_config.get("tts")
            tts = await get_tts_component(tts_cfg)

        if agent_config.get("stt"):
            stt_cfg = agent_config.get("stt")
            stt = await get_stt_component(stt_cfg)

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


def _build_agent_class(tools: Optional[List[Any]]) -> type:
    """Compose AgentSetup with any user-provided tool mixins."""
    agent_cls = AgentSetup
    user_tool_classes = tools or []
    if not isinstance(user_tool_classes, (list, tuple)):
        user_tool_classes = [user_tool_classes]
    if user_tool_classes:
        agent_cls = type(
            "UserAgentSetup",
            tuple([AgentSetup] + list(user_tool_classes)),
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
    turn_detector = MultilingualModel()

    return AgentSession(
        llm=session_llm,
        tts=session_tts,
        stt=session_stt,
        vad=vad_instance,
        turn_detection=turn_detector,
        allow_interruptions=allow_interruptions,
        min_endpointing_delay=min_endpointing_delay,
        max_endpointing_delay=max_endpointing_delay,
        min_interruption_duration=min_interruption_duration,
    )


async def entrypoint(
    ctx: JobContext, 
    llm: Optional[Dict[str, Any]] = None,
    stt: Optional[Dict[str, Any]] = None,
    tts: Optional[Dict[str, Any]] = None,
    send_greeting: Optional[bool] = True,
    greeting_instructions: Optional[str] = "Greet and introduce yourself briefly",
    system_instructions: Optional[str] = "You are a helpful voice assistant",
    allow_interruptions: Optional[bool] = True,
    min_silence_duration: Optional[float] = 0.25,
    activation_threshold: Optional[float] = 0.55,
    prefix_padding_duration: Optional[float] = 0.25,
    min_endpointing_delay: Optional[float] = 0.45,
    max_endpointing_delay: Optional[float] = 0.9,
    min_interruption_duration: Optional[float] = 0.08,
    tools: Optional[List[Any]] = None,
): 
    """LiveKit worker entrypoint for voice agents.

    This function is invoked by LiveKit Agents for each job. It inspects the
    job metadata to determine whether the call is inbound or outbound,
    reconstructs the LLM/STT/TTS components from config, and starts an
    AgentSession bound to the current room.
    """
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
        ) = await _derive_agent_config(
            metadata,
            llm,
            stt,
            tts,
            greeting_instructions,
            system_instructions,
        )

        agent_cls = _build_agent_class(tools)

        agent_setup = agent_cls(
            config=metadata,
            send_greeting=send_greeting,
            greeting_instructions=greeting_instructions,
            system_instructions=system_instructions,
            interruptions_allowed=allow_interruptions,
            room=ctx.room,
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
