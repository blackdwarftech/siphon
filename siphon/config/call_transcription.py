import os
from livekit.agents import ConversationItemAddedEvent
from livekit.agents.llm import ImageContent, AudioContent
from datetime import datetime
from livekit.agents import get_job_context
from .logging_config import get_logger
from .timezone_utils import get_timezone
from .data_storage import get_data_store

logger = get_logger("calling-agent")

class CallTranscription:
    """Capture and persist per-call conversation transcripts.

    The agent attaches this mixin to collect user and assistant messages
    as they are committed to the LiveKit conversation history and then
    persists them via the shared data storage layer.
    """

    def __init__(self) -> None:
        self.conversation_history: list[dict] = []
        self.tz = get_timezone()

        # Location string interpreted the same way as METADATA_LOCATION:
        # - "s3" → S3/MinIO bucket
        # - DB URLs (Mongo/Postgres/MySQL/Redis) → corresponding backends
        # - anything else → local folder path
        self.transcription_location = os.getenv("TRANSCRIPTION_LOCATION", "Transcriptions")

    async def _save_conversation(self) -> None:
        """Persist the collected conversation using the configured backend."""
        try:
            ctx = get_job_context()
            if ctx is None:
                raise Exception("No job context available")

            payload = {"conversation": self.conversation_history}

            store = get_data_store(self.transcription_location, kind="transcription")
            await store.save(payload, ctx.room.name)
            logger.info("Call transcription saved")
        except Exception as e:
            logger.error(f"Error saving call transcription: {e}")

    def _on_conversation_item_added(self, event: ConversationItemAddedEvent) -> None:
        """Process both user and agent messages when they are committed to chat history."""
        item = event.item
        role = item.role  # Will be "user" or "assistant"
        
        # Extract text content
        content = item.text_content
        if not content and item.content:
            # Handle different content types
            content_parts = []
            for content_item in item.content:
                if isinstance(content_item, str):
                    content_parts.append(content_item)
                elif isinstance(content_item, ImageContent):
                    content_parts.append("[image]")
                elif isinstance(content_item, AudioContent):
                    content_parts.append(f"[audio: {content_item.transcript}]")
            content = " ".join(content_parts)
        
        if content:
            logger.info(f"{role.capitalize()} message: {content}")
            self.conversation_history.append({
                "role": role,
                "content": content,
                "interrupted": getattr(item, 'interrupted', False),
                "timestamp": datetime.now(self.tz).strftime("%Y-%m-%d %I:%M:%S %p %Z")
            })

    async def setup_conversation_monitoring(self, session) -> None:
        """Set up event listeners for conversation monitoring."""
        # Listen to conversation_item_added event for both user and agent messages
        session.on("conversation_item_added", self._on_conversation_item_added)
        logger.info("Conversation monitoring setup complete")
