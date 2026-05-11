"""S3/MinIO storage backend for call memory."""

import json
import re
from datetime import datetime
from typing import Optional

import aioboto3
from botocore.config import Config

from .base import MemoryStore
from siphon.memory.models import CallerMemory
from siphon.config import get_logger
from siphon.config import _redact_phone
from siphon.config.s3_utils import ensure_s3_bucket_async, get_s3_config

logger = get_logger("calling-agent")


class S3MemoryStore(MemoryStore):
    """S3/MinIO storage for call memory."""

    def __init__(self) -> None:
        self.config = self._get_s3_config()
        self._session = aioboto3.Session(
            aws_access_key_id=self.config["access_key"],
            aws_secret_access_key=self.config["secret"],
            region_name=self.config["region"],
        )

    def _get_s3_config(self) -> dict:
        """Get S3 configuration from environment."""
        return get_s3_config()

    def _get_key(self, phone_number: str) -> str:
        """Get S3 key for phone number."""
        # Normalize: remove all non-digit characters to prevent collisions
        safe_phone = re.sub(r'\D', '', phone_number)
        if not safe_phone:
            safe_phone = "unknown"
        return f"call_memory/{safe_phone}.json"

    def _create_s3_client(self):
        """Create an async context manager for an S3 client."""
        client_kwargs: dict = {}
        if self.config["endpoint"]:
            client_kwargs["endpoint_url"] = self.config["endpoint"]
        config_kwargs = {
            "connect_timeout": 2,
            "read_timeout": 2,
            "retries": {"max_attempts": 3}
        }
        if self.config["force_path_style"]:
            config_kwargs["s3"] = {"addressing_style": "path"}
        client_kwargs["config"] = Config(**config_kwargs)
        
        return self._session.client("s3", **client_kwargs)

    async def get(self, phone_number: str) -> Optional[CallerMemory]:
        """Load memory from S3."""
        try:
            key = self._get_key(phone_number)
            async with self._create_s3_client() as s3_client:
                await ensure_s3_bucket_async(s3_client, self.config["bucket"], self.config["region"])
                response = await s3_client.get_object(Bucket=self.config["bucket"], Key=key)
                body = await response["Body"].read()
                data = json.loads(body.decode("utf-8"))
                memory = CallerMemory.model_validate(data)
                logger.info(f"Loaded memory from S3 for {_redact_phone(phone_number)}: {memory.total_calls} calls, {len(memory.summaries)} summaries")
                return memory
        except Exception as e:
            # Check for NoSuchKey using the error response code
            is_not_found = False
            if hasattr(e, 'response') and e.response:
                error_code = e.response.get('Error', {}).get('Code', '')
                is_not_found = error_code == 'NoSuchKey'
            elif "NoSuchKey" in str(e):
                is_not_found = True
            
            if is_not_found:
                logger.debug(f"No memory found in S3 for {_redact_phone(phone_number)}")
                return None
            logger.error(f"Error loading memory from S3 for {_redact_phone(phone_number)}: {e}")
            return None

    async def save(self, phone_number: str, memory: CallerMemory) -> None:
        """Save memory to S3."""
        try:
            key = self._get_key(phone_number)
            data = memory.model_dump()
            body = json.dumps(data, ensure_ascii=False, default=lambda v: v.isoformat() if isinstance(v, datetime) else str(v)).encode("utf-8")
            
            async with self._create_s3_client() as s3_client:
                await ensure_s3_bucket_async(s3_client, self.config["bucket"], self.config["region"])
                await s3_client.put_object(
                    Bucket=self.config["bucket"],
                    Key=key,
                    Body=body,
                    ContentType="application/json",
                )
            logger.info(f"Saved memory to S3 for {_redact_phone(phone_number)}: {memory.total_calls} calls, {len(memory.summaries)} summaries")
        except Exception as e:
            logger.error(f"Error saving memory to S3 for {_redact_phone(phone_number)}: {e}")

    async def delete(self, phone_number: str) -> bool:
        """Delete memory from S3."""
        try:
            key = self._get_key(phone_number)
            async with self._create_s3_client() as s3_client:
                await ensure_s3_bucket_async(s3_client, self.config["bucket"], self.config["region"])
                await s3_client.delete_object(Bucket=self.config["bucket"], Key=key)
            return True
        except Exception:
            return False

    async def exists(self, phone_number: str) -> bool:
        """Check if memory exists in S3."""
        try:
            key = self._get_key(phone_number)
            async with self._create_s3_client() as s3_client:
                await ensure_s3_bucket_async(s3_client, self.config["bucket"], self.config["region"])
                await s3_client.head_object(Bucket=self.config["bucket"], Key=key)
            return True
        except Exception:
            return False
