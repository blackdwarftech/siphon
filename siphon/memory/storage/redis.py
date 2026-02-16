"""Redis storage backend for call memory."""

import json
from typing import Optional

from .base import MemoryStore
from siphon.memory.models import CallerMemory


class RedisMemoryStore(MemoryStore):
    """Redis storage for call memory."""

    def __init__(self, url: str) -> None:
        try:
            import redis
        except ImportError as exc:
            raise RuntimeError("redis is required for Redis memory storage") from exc

        self._client = redis.from_url(url)

    def _get_key(self, phone_number: str) -> str:
        """Get Redis key for phone number."""
        safe_phone = phone_number.lstrip("+").replace(" ", "_").replace("-", "_")
        return f"call_memory:{safe_phone}"

    async def get(self, phone_number: str) -> Optional[CallerMemory]:
        """Load memory from Redis."""
        key = self._get_key(phone_number)
        data = self._client.get(key)
        if data:
            return CallerMemory.model_validate(json.loads(data.decode("utf-8")))
        return None

    async def save(self, phone_number: str, memory: CallerMemory) -> None:
        """Save memory to Redis."""
        key = self._get_key(phone_number)
        data = json.dumps(memory.model_dump(), ensure_ascii=False, default=str).encode("utf-8")
        self._client.set(key, data)

    async def delete(self, phone_number: str) -> bool:
        """Delete memory from Redis."""
        key = self._get_key(phone_number)
        result = self._client.delete(key)
        return result > 0

    async def exists(self, phone_number: str) -> bool:
        """Check if memory exists in Redis."""
        key = self._get_key(phone_number)
        return self._client.exists(key) > 0
