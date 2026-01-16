from livekit import api
from livekit.agents import get_job_context
from datetime import datetime
import os
import boto3
from botocore.config import Config
from .logging_config import get_logger
from .timezone_utils import get_timezone

logger = get_logger("calling-agent")

class CallRecording:
    def __init__(self) -> None:
        """Initialize recording state for a call."""
        self.recording_id = None
        self.is_recording = False
        self.filename = None
        self.s3_bucket = None
        
    async def _get_s3_config(self):
        """Return S3/MinIO configuration derived from environment variables."""
        s3_endpoint = os.getenv("AWS_S3_ENDPOINT")  # MinIO: http://localhost:9000

        s3_access_key = (os.getenv("AWS_S3_ACCESS_KEY_ID") or 
                        os.getenv("AWS_ACCESS_KEY_ID") or 
                        os.getenv("MINIO_ACCESS_KEY"))

        s3_secret_key = (os.getenv("AWS_S3_SECRET_ACCESS_KEY") or 
                        os.getenv("AWS_SECRET_ACCESS_KEY") or 
                        os.getenv("MINIO_SECRET_KEY"))

        s3_bucket = (os.getenv("AWS_S3_BUCKET") or 
                    os.getenv("MINIO_BUCKET"))

        s3_region = os.getenv("AWS_S3_REGION", "us-east-1")
        s3_force_path_style = os.getenv("AWS_S3_FORCE_PATH_STYLE", "false").lower() == "true"
        
        if not all([s3_access_key, s3_secret_key, s3_bucket]):
            raise Exception(
                "S3/MinIO credentials missing. Set:\n"
                "  AWS_S3_ACCESS_KEY_ID / MINIO_ACCESS_KEY\n"
                "  AWS_S3_SECRET_ACCESS_KEY / MINIO_SECRET_KEY\n"
                "  AWS_S3_BUCKET / MINIO_BUCKET"
            )
        
        self.s3_bucket = s3_bucket
        return {
            "access_key": s3_access_key,
            "secret": s3_secret_key,
            "bucket": s3_bucket,
            "region": s3_region,
            "endpoint": s3_endpoint,
            "force_path_style": s3_force_path_style,
        }
    
    async def _get_livekit_api(self):
        """Return LiveKit API bound to the current job context."""
        ctx = get_job_context()
        if ctx is None:
            raise Exception("No job context available")
        return ctx.api
        
    async def start_recording(self) -> str:
        """Start a room composite egress and write output to S3/MinIO."""
        try:
            ctx = get_job_context()
            if ctx is None:
                raise Exception("No job context available")
            
            livekit_api = await self._get_livekit_api()

            # Build per-room, per-call key: <room>/<timestamp>/call_...ogg
            tz = get_timezone()
            now = datetime.now(tz) if tz is not None else datetime.now()
            timestamp = now.strftime("%d-%m-%Y-%I-%M-%p")
            safe_room_name = ctx.room.name.replace(" ", "_")
            folder = f"{safe_room_name}/{timestamp}"
            self.filename = f"call_{safe_room_name}_{timestamp}.ogg"
            s3_key = f"{folder}/{self.filename}"
            self.s3_key = s3_key

            s3_config = await self._get_s3_config()

            logger.info(f"🚀 Starting recording to {s3_config['bucket']}/{s3_key}")

            file_output = api.EncodedFileOutput(
                file_type=api.EncodedFileType.OGG,
                filepath=s3_key,
                s3=api.S3Upload(
                    access_key=s3_config["access_key"],
                    secret=s3_config["secret"],
                    bucket=s3_config["bucket"],
                    region=s3_config["region"],
                    force_path_style=s3_config["force_path_style"],
                    endpoint=s3_config["endpoint"] or None,
                ),
            )
            
            # Start room composite egress (recording)
            request = api.RoomCompositeEgressRequest(
                room_name=ctx.room.name,
                layout="speaker",
                audio_only=True,
                file_outputs=[file_output],
            )
            
            response = await livekit_api.egress.start_room_composite_egress(request)
            self.recording_id = response.egress_id
            self.is_recording = True
            
            logger.info(f"✅ Recording started: ID={self.recording_id}")
            logger.info(f"📁 S3 Path: s3://{s3_config['bucket']}/{self.s3_key}")
            logger.info(f"📊 Status: {response.status}")
            
            return self.recording_id
            
        except Exception as e:
            logger.error(f"❌ Failed to start recording: {e}")
            raise
    
    async def stop_recording(self):
        """Stop egress for the current call and log the resulting file info."""
        try:
            if not self.is_recording or not self.recording_id:
                logger.warning("No active recording to stop")
                return None
            
            livekit_api = await self._get_livekit_api()
            
            # Stop the egress (recording)
            request = api.StopEgressRequest(egress_id=self.recording_id)
            response = await livekit_api.egress.stop_egress(request)
            
            self.is_recording = False
            recording_id = self.recording_id
            self.recording_id = None

            # Prefer full key (folder + filename) if available
            key = getattr(self, "s3_key", self.filename)
            s3_path = f"s3://{self.s3_bucket}/{key}"
            
            logger.info(f"🛑 Stopped recording: ID={recording_id}")
            logger.info(f"📊 Final status: {response.status}")
            logger.info(f"💾 Saved to: {s3_path}")
            
            # Log file results if available
            if hasattr(response, 'file_results') and response.file_results:
                for file_result in response.file_results:
                    logger.info(f"📎 Filename: {file_result.filename}")
                    
                    if hasattr(file_result, 'download_url'):
                        logger.info(f"🔗 Download: {file_result.download_url}")
            
            return response
            
        except Exception as e:
            logger.error(f"❌ Error stopping recording: {e}")
            raise
    
    def get_s3_path(self) -> str | None:
        key = getattr(self, "s3_key", self.filename)
        return f"s3://{self.s3_bucket}/{key}" if key and self.s3_bucket else None
    
    async def ensure_recording(self):
        if not self.is_recording:
            await self.start_recording()
    
    async def cleanup(self):
        if self.is_recording:
            await self.stop_recording()

    async def discard_recording(self):
        """Stop egress and delete the current recording object from S3/MinIO."""
        try:
            # Stop egress if it's still running
            if self.is_recording or self.recording_id:
                try:
                    await self.stop_recording()
                except Exception as e:
                    logger.error(f"Error stopping recording while discarding: {e}")

            # Ensure we have S3 configuration and key
            s3_config = await self._get_s3_config()
            key = getattr(self, "s3_key", self.filename)
            if not key:
                logger.warning("No S3 key found for recording; nothing to discard")
                return

            session = boto3.session.Session(
                aws_access_key_id=s3_config["access_key"],
                aws_secret_access_key=s3_config["secret"],
                region_name=s3_config["region"],
            )

            client_kwargs = {}
            if s3_config["endpoint"]:
                client_kwargs["endpoint_url"] = s3_config["endpoint"]

            if s3_config["force_path_style"]:
                client_kwargs["config"] = Config(s3={"addressing_style": "path"})

            s3_client = session.client("s3", **client_kwargs)
            s3_client.delete_object(Bucket=s3_config["bucket"], Key=key)
            logger.info(f"🗑️ Discarded recording from s3://{s3_config['bucket']}/{key}")

        except Exception as e:
            logger.error(f"❌ Failed to discard recording: {e}")
