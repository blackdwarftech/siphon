"""Redis storage backend for call memory."""

import json
from typing import Optional

from .base import MemoryStore
from siphon.memory.models import CallerMemory
from siphon.config import get_logger

logger = get_logger("calling-agent")


class RedisMemoryStore(MemoryStore):
    """Redis storage for call memory."""

    def __init__(self, url: str) -> None:
        try:
            import redis.asyncio as redis
        except ImportError as exc:
            raise RuntimeError("redis is required for Redis memory storage") from exc

        self._client = redis.from_url(
            url,
            socket_connect_timeout=2.0,
            socket_timeout=2.0,
            retry_on_timeout=False
        )

    def _get_key(self, phone_number: str) -> str:
        """Get Redis key for phone number."""
        safe_phone = phone_number.lstrip("+").replace(" ", "_").replace("-", "_")
        return f"call_memory:{safe_phone}"

    async def get(self, phone_number: str) -> Optional[CallerMemory]:
        """Load memory from Redis."""
        try:
            key = self._get_key(phone_number)
            data = await self._client.get(key)
            if data:
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                memory = CallerMemory.model_validate(json.loads(data))
                logger.info(f"Loaded memory from Redis for {phone_number}: {memory.total_calls} calls, {len(memory.summaries)} summaries")
                return memory
            logger.debug(f"No memory found in Redis for {phone_number}")
            return None
        except Exception as e:
            logger.error(f"Error loading memory from Redis for {phone_number}: {e}")
            return None

    async def save(self, phone_number: str, memory: CallerMemory) -> None:
        """Save memory to Redis."""
        try:
            key = self._get_key(phone_number)
            data = json.dumps(memory.model_dump(), ensure_ascii=False, default=str)
            await self._client.set(key, data)
            logger.info(f"Saved memory to Redis for {phone_number}: {memory.total_calls} calls, {len(memory.summaries)} summaries")
        except Exception as e:
            logger.error(f"Error saving memory to Redis for {phone_number}: {e}")

    async def delete(self, phone_number: str) -> bool:
        """Delete memory from Redis."""
        try:
            key = self._get_key(phone_number)
            result = await self._client.delete(key)
            return result > 0
        except Exception as e:
            logger.error(f"Error deleting memory from Redis for {phone_number}: {e}")
            return False

    async def exists(self, phone_number: str) -> bool:
        """Check if memory exists in Redis."""
        try:
            key = self._get_key(phone_number)
            return await self._client.exists(key) > 0
        except Exception as e:
            logger.error(f"Error checking if memory exists in Redis for {phone_number}: {e}")
            return False

