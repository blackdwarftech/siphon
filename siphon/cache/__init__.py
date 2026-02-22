"""SIPHON Cache Module - Centralized caching for trunks, memory, and dispatch rules.

This module provides a caching layer for:
- SIP trunk IDs (outbound and inbound)
- Caller memory
- Dispatch rules

Uses Redis as the cache backend with automatic fallback if Redis is unavailable.

Environment Variables:
    REDIS_URL: Redis connection URL (e.g., redis://localhost:6379/0)
    CACHE_REDIS_URL: Alternative Redis URL (takes precedence)
    CACHE_TTL: Cache TTL in seconds (default: 86400 = 24 hours)
    CACHE_MAX_CONNECTIONS: Max Redis connections per process (default: 20)

Usage:
    from siphon.cache import get_cache_service
    
    cache = get_cache_service()
    
    # Cache trunk ID
    await cache.set_trunk_id_outbound(sip_number, sip_address, sip_username, trunk_id)
    
    # Get cached trunk ID
    trunk_id = await cache.get_trunk_id_outbound(sip_number, sip_address, sip_username)
    
    # Cache memory
    await cache.set_memory(phone_number, memory_data)
    
    # Get cached memory
    memory = await cache.get_memory(phone_number)
    
    # Invalidate cache
    await cache.invalidate_trunk_outbound(sip_number, sip_address, sip_username)
    await cache.invalidate_memory(phone_number)

Production Notes:
    - Each worker process maintains its own Redis connection pool
    - Automatic reconnection if Redis becomes unavailable
    - Stampede protection to prevent multiple API calls for same key
    - Set CACHE_MAX_CONNECTIONS based on: (total_redis_connections / number_of_workers)
"""

from siphon.cache.backend import CacheBackend
from siphon.cache.service import CacheService, get_cache_service

__all__ = [
    "CacheBackend",
    "CacheService",
    "get_cache_service",
]
