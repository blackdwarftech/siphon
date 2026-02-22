"""Storage backend exports and factory."""

import os
from typing import Optional
from siphon.memory.storage.base import MemoryStore
from siphon.memory.storage.local import LocalMemoryStore


def create_memory_store(location: Optional[str] = None) -> MemoryStore:
    """Factory function to create appropriate memory store.
    
    Args:
        location: Storage location. If None, uses CALL_MEMORY_LOCATION env var.
                 Supports:
                 - local folder path (default "Call_Memory")
                 - "s3" for S3/MinIO storage
                 - "redis://host:port" for Redis
                 - "mongodb://host/db" for MongoDB
                 - "postgresql://host/db" for PostgreSQL
                 - "mysql://host/db" for MySQL
    
    Returns:
        MemoryStore instance
    """
    if not location:
        location = os.getenv("CALL_MEMORY_LOCATION", "Call_Memory")
    
    location = location.strip()
    lower = location.lower()
    
    # S3/MinIO
    if lower == "s3":
        from siphon.memory.storage.s3 import S3MemoryStore
        return S3MemoryStore()
    
    # Redis
    if lower.startswith("redis://") or lower.startswith("rediss://"):
        from siphon.memory.storage.redis import RedisMemoryStore
        return RedisMemoryStore(location)
    
    # MongoDB
    if lower.startswith("mongodb://") or lower.startswith("mongodb+srv://"):
        from siphon.memory.storage.mongodb import MongoDBMemoryStore
        return MongoDBMemoryStore(location)
    
    # PostgreSQL
    if lower.startswith("postgres://") or lower.startswith("postgresql://"):
        from siphon.memory.storage.sql import SQLMemoryStore
        return SQLMemoryStore(location)
    
    # MySQL
    if lower.startswith("mysql://") or lower.startswith("mysql+pymysql://"):
        from siphon.memory.storage.sql import SQLMemoryStore
        return SQLMemoryStore(location)
    
    # Default: Local storage
    return LocalMemoryStore(location)


__all__ = ["MemoryStore", "LocalMemoryStore", "create_memory_store"]
