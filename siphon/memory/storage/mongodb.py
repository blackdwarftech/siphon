"""MongoDB storage backend for call memory."""

from typing import Optional
from urllib.parse import urlparse

from .base import MemoryStore
from siphon.memory.models import CallerMemory


class MongoDBMemoryStore(MemoryStore):
    """MongoDB storage for call memory."""

    def __init__(self, url: str) -> None:
        try:
            from pymongo import MongoClient
        except ImportError as exc:
            raise RuntimeError("pymongo is required for MongoDB memory storage") from exc

        parsed = urlparse(url)
        db_name = parsed.path.lstrip("/") or "call_memory"
        client = MongoClient(url)
        self.collection = client[db_name]["caller_memories"]
        # Create index on phone_number for fast lookups
        self.collection.create_index("phone_number", unique=True)

    async def get(self, phone_number: str) -> Optional[CallerMemory]:
        """Load memory from MongoDB."""
        doc = self.collection.find_one({"phone_number": phone_number})
        if doc:
            doc.pop("_id", None)  # Remove MongoDB ObjectId
            return CallerMemory.model_validate(doc)
        return None

    async def save(self, phone_number: str, memory: CallerMemory) -> None:
        """Save memory to MongoDB."""
        # Convert to dict for MongoDB storage
        data = memory.model_dump()
        # Upsert: update if exists, insert if not
        self.collection.update_one(
            {"phone_number": phone_number},
            {"$set": data},
            upsert=True
        )

    async def delete(self, phone_number: str) -> bool:
        """Delete memory from MongoDB."""
        result = self.collection.delete_one({"phone_number": phone_number})
        return result.deleted_count > 0

    async def exists(self, phone_number: str) -> bool:
        """Check if memory exists in MongoDB."""
        return self.collection.count_documents({"phone_number": phone_number}) > 0
