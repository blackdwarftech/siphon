import time
from livekit.agents import get_job_context
from .logging_config import get_logger
from .timezone_utils import get_timezone_name, format_timestamp
from .data_storage import get_data_store
import os

logger = get_logger("calling-agent")


class CallMetadata:
    """Collects and persists per-call metadata for answered and unanswered calls.

    This class is responsible for building a consistent metadata payload
    (direction, phone numbers, trunks, timing, status, recording info, etc.)
    and delegating persistence to the shared data storage layer.
    """

    # Constants
    TIMEZONE_ENV_VAR = "TIMEZONE"
    SHORT_CALL_THRESHOLD = 3  # seconds
    METADATA_LOCATION = "METADATA_LOCATION"

    # Status mapping for responses
    STATUS_MAPPING = {
        1: "completed",      # EGRESS_STATUS_ACTIVE
        2: "completed",      # EGRESS_STATUS_ENDED
        3: "failed",         # EGRESS_STATUS_FAILED
        4: "aborted",        # EGRESS_STATUS_ABORTED
        5: "limit_reached",  # EGRESS_STATUS_LIMIT_REACHED
    }

    def __init__(self, config):
        ctx = get_job_context()
        self.ctx = ctx

        self.config = config

        self.phone_numbers = {
            "agent_number": "",
            "user_number": "",
        }
        # Idempotency flag to avoid duplicate metadata saves
        self._metadata_saved = False

    def _extract_basic_metadata(self) -> dict:
        """Extract basic metadata from config"""
        room_name = self.ctx.room.name
        return {"room_name": room_name}

    def _determine_call_direction(self) -> tuple:
        """Determine call direction and return direction info"""
        outbound_trunk_id = self.config.get("outbound_trunk_id")
        inbound_trunk_id = self.config.get("inbound_trunk_id")
        number_to_call = self.config.get("number_to_call")

        if number_to_call or outbound_trunk_id:
            direction = "outbound"
            trunk_info = {
                "outbound_trunk_id": outbound_trunk_id,
                "inbound_trunk_id": "",
            }
        else:
            direction = "inbound"
            trunk_info = {
                "outbound_trunk_id": "",
                "inbound_trunk_id": inbound_trunk_id,
            }
            
        logger.info(f"Call direction determined as: {direction}")
        return direction, trunk_info

    def _get_phone_numbers(self, direction: str) -> dict:
        """Get phone numbers based on call direction"""
        if direction == "outbound":
            numbers = {
                "agent_number": self.config.get("agent_number", ""),
                "user_number": self.config.get("number_to_call", ""),
            }
        else:
            numbers = {
                "agent_number": self.config.get("agent_number", ""),
                "user_number": "",
            }

        # Preserve any previously cached values (e.g., set early via update_inbound_phone_numbers)
        final_numbers = {}
        for k, v in numbers.items():
            prev = self.phone_numbers.get(k)
            final_numbers[k] = prev if prev else v

        # Store the numbers for later updates
        self.phone_numbers.update(final_numbers)
        return self.phone_numbers

    def update_inbound_phone_numbers(self, caller_number: str) -> None:
        """Update customer phone number for inbound calls"""
        self.phone_numbers["user_number"] = caller_number

    def _build_base_metadata(self) -> dict:
        """Build base metadata common to both answered and unanswered calls"""
        metadata = self._extract_basic_metadata()
        
        # Determine call direction
        direction, trunk_info = self._determine_call_direction()
        metadata['call_direction'] = direction
        metadata.update(trunk_info)
        
        # Get phone numbers
        phone_numbers = self._get_phone_numbers(direction)
        metadata.update(phone_numbers)
        
        return metadata

    async def _set_timing_metadata(self, metadata: dict, start_time: float = None, end_time: float = None) -> None:
        """Set timing-related metadata, including formatted timestamps."""
        if start_time is None:
            start_time = time.time()
        if end_time is None:
            end_time = time.time()

        metadata['start_time'] = format_timestamp(start_time)
        metadata['end_time'] = format_timestamp(end_time)
        metadata['duration'] = end_time - start_time
        metadata['timezone'] = get_timezone_name() or "local"

    def _determine_call_status(self, response, duration: float) -> tuple:
        """Determine call status and termination reason"""
        if not response:
            has_conversation = hasattr(self, 'conversation_history') and len(self.conversation_history) > 0
            if has_conversation:
                return 'completed_no_recording', 'recording not available'
            else:
                return 'no_recording', 'recording not started'
        
        # Status from response
        if hasattr(response, 'status'):
            status = self.STATUS_MAPPING.get(response.status, 'completed')
        else:
            status = 'completed'
        
        return status

    def _get_recording_filename(self, response) -> str:
        """Extract recording filename from response"""
        if hasattr(response, 'file_results') and response.file_results:
            file_result = response.file_results[0]
            return getattr(file_result, 'filename', 'unknown')
        return ''

    async def _save_metadata_to_storage(self, metadata: dict) -> None:
        """Save metadata to both MongoDB and local file"""
        metadata_location = os.getenv("METADATA_LOCATION", "Call_Metadata")

        metadata_copy = metadata.copy()
        if "_id" in metadata_copy:
            del metadata_copy["_id"]  # Remove ObjectId before saving to JSON

        s3_key = None
        recording_filename = metadata_copy.get("recording_filename")
        if isinstance(recording_filename, str) and recording_filename:
            s3_key = recording_filename

        store = get_data_store(metadata_location)
        await store.save(metadata_copy, self.ctx.room.name, s3_key=s3_key)

    async def save_unanswered_call_metadata(self, reason: str = "not_answered") -> None:
        """
        Save metadata for calls that are not picked up or fail to connect
        
        Args:
            reason: Reason for call not connecting (default='not_answered')
        
        Returns:
            None
        """
        try:
            # Prevent duplicate saves
            if getattr(self, "_metadata_saved", False):
                logger.warning("Metadata already saved, skipping unanswered-call duplicate save")
                return
            logger.info(f"Saving unanswered call metadata. Reason: {reason}")
            
            # Build base metadata
            metadata = self._build_base_metadata()
            
            # Set timing for unanswered call
            current_time = time.time()
            await self._set_timing_metadata(metadata, current_time, current_time)
            metadata['duration'] = 0
            
            # Set status and termination reason
            metadata['status'] = reason
            # Explicit answered flag for downstream consumers
            metadata['answered'] = False
            metadata['recording_filename'] = ''
            
            logger.info(f"Unanswered call metadata - Status: {metadata['status']}, Reason: {reason}")
            
            # Save to Database
            await self._save_metadata_to_storage(metadata)
            self._metadata_saved = True
        
        except Exception as e:
            logger.error(f"Error saving unanswered call metadata (non-critical): {e}")

    async def save_call_metadata(self, response) -> None:
        """
        Save metadata for calls that are connected and picked up
        
        Args:
            response: The data to determine wheather the call is picked up or not.The call status.
        
        Returns:
            None
        """
        try:
            # Prevent duplicate saves
            if getattr(self, "_metadata_saved", False):
                logger.warning("Metadata already saved, skipping duplicate save")
                return
            logger.info(f"Saving call metadata. Response: {response}")
            
            # Build base metadata
            metadata = self._build_base_metadata()

            # Safe logging of numbers using the current field names
            logger.info(
                "Numbers saved - Agent: %s, User: %s",
                metadata.get('agent_number', ''),
                metadata.get('user_number', ''),
            )
            
            if response:
                # Extract timestamps from response
                start_timestamp = response.started_at / 1e9 if hasattr(response, 'started_at') and response.started_at else time.time()
                end_timestamp = response.ended_at / 1e9 if hasattr(response, 'ended_at') and response.ended_at else time.time()
                
                # Set timing metadata
                await self._set_timing_metadata(metadata, start_timestamp, end_timestamp)
                
                # Determine status and termination reason
                status = self._determine_call_status(response, metadata['duration'])
                metadata['status'] = status
                # Call reached a state where recording response exists -> treat as answered
                metadata['answered'] = True
                
                # Get recording filename
                metadata['recording_filename'] = self._get_recording_filename(response)
                
            else:
                # No recording response - fall back to call_start_time if available
                current_time = time.time()
                start_timestamp = getattr(self, 'call_start_time', current_time)

                await self._set_timing_metadata(metadata, start_timestamp, current_time)
                
                # Determine status for no-response scenario using the actual duration
                status = self._determine_call_status(
                    response,
                    metadata['duration'],
                )
                metadata['status'] = status
                metadata['recording_filename'] = ''

                # Heuristic answered flag when we have no recording response:
                # - very short, no conversation => treat as unanswered
                # - otherwise assume answered but not recorded
                duration = metadata.get('duration', 0)
                has_conversation = hasattr(self, 'conversation_history') and len(self.conversation_history) > 0
                if duration < self.SHORT_CALL_THRESHOLD and not has_conversation:
                    metadata['answered'] = False
                else:
                    metadata['answered'] = True
            
            # Save to Database
            await self._save_metadata_to_storage(metadata)
            self._metadata_saved = True
        
        except Exception as e:
            logger.error(f"Error saving call metadata (non-critical): {e}")
