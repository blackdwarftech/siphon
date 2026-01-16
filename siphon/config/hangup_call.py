from livekit import api
from livekit.agents import get_job_context
from livekit.agents import RunContext, function_tool
from .call_recording import CallRecording
from .call_metadata import CallMetadata
from .logging_config import get_logger
from typing import Any

logger = get_logger("calling-agent")

class HangupCall(CallRecording,CallMetadata):
    """Call control helpers built on top of CallRecording."""

    def __init__(
        self,
        config: Any,
        response: Any,
        hangup_call: bool,
        call_recording: bool,
        save_metadata: bool,
    ) -> None:
        CallRecording.__init__(self)
        CallMetadata.__init__(self, config)

        # When False, tools become a no-op for this agent.
        self._hangup_enabled = hangup_call
        self._call_recording = call_recording
        self._save_metadata = save_metadata
        self.response = response

        # Tracks whether this call was never actually answered. When True,
        # other lifecycle hooks (e.g. AgentSetup.on_exit) should avoid
        # saving additional metadata, recordings, or transcriptions.
        self._unanswered_call = False

    @function_tool
    async def end_call(self, ctx: RunContext):
        """Tool: end the current call when the user asks to hang up or a scenario comes where you need to hangup."""

        if not getattr(self, "_hangup_enabled", False):
            # Tool is present but disabled for this agent/call.
            return

        # Let the agent finish speaking before hanging up.
        await ctx.wait_for_playout()
        await self._hangup_room()

    async def _hangup_room(self) -> None:
        """Delete the current room from the LiveKit job context, if any."""

        ctx = get_job_context()
        if ctx is None:
            return

        if self._call_recording:
            try:
                self.response = await self.stop_recording()
                logger.info(f"Stopped recording before ending call. Response: {self.response}")
            except Exception as e:
                logger.error(f"Error stopping recording before ending call: {e}")
                self.response = None

        if self._save_metadata:
            await self.save_call_metadata(self.response)

        await ctx.api.room.delete_room(
            api.DeleteRoomRequest(
                room=ctx.room.name,
            )
        )

    async def handle_unanswered_call(self):
        """Discard recording and room state for calls that were never answered."""
        ctx = get_job_context()
        if ctx is None:
            return

        # Mark this call as unanswered so downstream hooks can make
        # decisions (e.g. skip saving metadata/transcripts again).
        self._unanswered_call = True

        if self._call_recording:
            try:
                await self.discard_recording()
                logger.info("Discarded recording for unanswered call")
            except Exception as e:
                logger.error(f"Error discarding recording for unanswered call: {e}")

        if self._save_metadata:
            # For calls that were never answered, record concise metadata
            # without any recording information.
            await self.save_unanswered_call_metadata()

        await ctx.api.room.delete_room(
            api.DeleteRoomRequest(
                room=ctx.room.name,
            )
        )