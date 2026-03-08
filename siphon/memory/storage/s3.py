"""S3/MinIO storage backend for call memory."""

import json
import os
from typing import Optional

import aioboto3
from botocore.config import Config

from .base import MemoryStore
from siphon.memory.models import CallerMemory
from siphon.config import get_logger

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
        s3_endpoint = os.getenv("AWS_S3_ENDPOINT")
        s3_access_key = (
            os.getenv("AWS_S3_ACCESS_KEY_ID")
            or os.getenv("AWS_ACCESS_KEY_ID")
            or os.getenv("MINIO_ACCESS_KEY")
        )
        s3_secret_key = (
            os.getenv("AWS_S3_SECRET_ACCESS_KEY")
            or os.getenv("AWS_SECRET_ACCESS_KEY")
            or os.getenv("MINIO_SECRET_KEY")
        )
        s3_bucket = os.getenv("AWS_S3_BUCKET") or os.getenv("MINIO_BUCKET")
        s3_region = os.getenv("AWS_S3_REGION", "us-east-1")
        s3_force_path_style = (
            os.getenv("AWS_S3_FORCE_PATH_STYLE", "false").lower() == "true"
        )

        if not all([s3_access_key, s3_secret_key, s3_bucket]):
            raise Exception(
                "S3/MinIO credentials missing. Set AWS_S3_ACCESS_KEY_ID / MINIO_ACCESS_KEY, "
                "AWS_S3_SECRET_ACCESS_KEY / MINIO_SECRET_KEY and AWS_S3_BUCKET / MINIO_BUCKET"
            )

        return {
            "access_key": s3_access_key,
            "secret": s3_secret_key,
            "bucket": s3_bucket,
            "region": s3_region,
            "endpoint": s3_endpoint,
            "force_path_style": s3_force_path_style,
        }

    def _get_key(self, phone_number: str) -> str:
        """Get S3 key for phone number."""
        safe_phone = phone_number.lstrip("+").replace(" ", "_").replace("-", "_")
        return f"call_memory/{safe_phone}.json"

    def _create_s3_client(self):
        """Create an async context manager for an S3 client."""
        client_kwargs: dict = {}
        if self.config["endpoint"]:
            client_kwargs["endpoint_url"] = self.config["endpoint"]
        config_kwargs = {
            "connect_timeout": 2,
            "read_timeout": 2,
            "retries": {"max_attempts": 0}
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
                response = await s3_client.get_object(Bucket=self.config["bucket"], Key=key)
                body = await response["Body"].read()
                data = json.loads(body.decode("utf-8"))
                memory = CallerMemory.model_validate(data)
                logger.info(f"Loaded memory from S3 for {phone_number}: {memory.total_calls} calls, {len(memory.summaries)} summaries")
                return memory
        except Exception as e:
            if "NoSuchKey" in str(e):
                logger.debug(f"No memory found in S3 for {phone_number}")
                return None
            logger.error(f"Error loading memory from S3 for {phone_number}: {e}")
            return None

    async def save(self, phone_number: str, memory: CallerMemory) -> None:
        """Save memory to S3."""
        try:
            key = self._get_key(phone_number)
            data = memory.model_dump()
            body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
            
            async with self._create_s3_client() as s3_client:
                await s3_client.put_object(
                    Bucket=self.config["bucket"],
                    Key=key,
                    Body=body,
                    ContentType="application/json",
                )
            logger.info(f"Saved memory to S3 for {phone_number}: {memory.total_calls} calls, {len(memory.summaries)} summaries")
        except Exception as e:
            logger.error(f"Error saving memory to S3 for {phone_number}: {e}")

    async def delete(self, phone_number: str) -> bool:
        """Delete memory from S3."""
        try:
            key = self._get_key(phone_number)
            async with self._create_s3_client() as s3_client:
                await s3_client.delete_object(Bucket=self.config["bucket"], Key=key)
            return True
        except Exception:
            return False

    async def exists(self, phone_number: str) -> bool:
        """Check if memory exists in S3."""
        try:
            key = self._get_key(phone_number)
            async with self._create_s3_client() as s3_client:
                await s3_client.head_object(Bucket=self.config["bucket"], Key=key)
            return True
        except Exception:
            return False
