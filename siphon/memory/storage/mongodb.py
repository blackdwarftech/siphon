"""MongoDB storage backend for call memory."""

from typing import Optional
from urllib.parse import urlparse

from .base import MemoryStore
from siphon.memory.models import CallerMemory
from siphon.config import get_logger

logger = get_logger("calling-agent")


class MongoDBMemoryStore(MemoryStore):
    """MongoDB storage for call memory."""

    def __init__(self, url: str) -> None:
        try:
            from motor.motor_asyncio import AsyncIOMotorClient
        except ImportError as exc:
            raise RuntimeError("motor is required for MongoDB memory storage") from exc

        parsed = urlparse(url)
        db_name = parsed.path.lstrip("/") or "call_memory"
        
        # Configure fail-fast timeouts (2 seconds) so unreachable DBs don't stall the agent
        self.client = AsyncIOMotorClient(
            url,
            serverSelectionTimeoutMS=2000,
            connectTimeoutMS=2000,
            socketTimeoutMS=2000
        )
        self.collection = self.client[db_name]["caller_memories"]
        self._initialized = False

    async def _ensure_initialized(self) -> None:
        """Create indexes if not already initialized."""
        if not self._initialized:
            try:
                await self.collection.create_index("phone_number", unique=True)
                self._initialized = True
            except Exception as e:
                logger.error(f"MongoDB index creation failed (db might be unreachable): {e}")

    async def get(self, phone_number: str) -> Optional[CallerMemory]:
        """Load memory from MongoDB."""
        await self._ensure_initialized()
        try:
            doc = await self.collection.find_one({"phone_number": phone_number})
            if doc:
                doc.pop("_id", None)  # Remove MongoDB ObjectId
                memory = CallerMemory.model_validate(doc)
                logger.info(f"Loaded memory from MongoDB for {phone_number}: {memory.total_calls} calls, {len(memory.summaries)} summaries")
                return memory
            logger.debug(f"No memory found in MongoDB for {phone_number}")
            return None
        except Exception as e:
            logger.error(f"MongoDB get failed for {phone_number}: {e}")
            return None

    async def save(self, phone_number: str, memory: CallerMemory) -> None:
        """Save memory to MongoDB."""
        await self._ensure_initialized()
        try:
            # Convert to dict for MongoDB storage
            data = memory.model_dump()
            # Upsert: update if exists, insert if not
            await self.collection.update_one(
                {"phone_number": phone_number},
                {"$set": data},
                upsert=True
            )
            logger.info(f"Saved memory to MongoDB for {phone_number}: {memory.total_calls} calls, {len(memory.summaries)} summaries")
        except Exception as e:
            logger.error(f"MongoDB save failed for {phone_number}: {e}")

    async def delete(self, phone_number: str) -> bool:
        """Delete memory from MongoDB."""
        await self._ensure_initialized()
        try:
            result = await self.collection.delete_one({"phone_number": phone_number})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"MongoDB delete failed for {phone_number}: {e}")
            return False

    async def exists(self, phone_number: str) -> bool:
        """Check if memory exists in MongoDB."""
        await self._ensure_initialized()
        try:
            count = await self.collection.count_documents({"phone_number": phone_number}, limit=1)
            return count > 0
        except Exception as e:
            logger.error(f"MongoDB exists check failed for {phone_number}: {e}")
            return False
