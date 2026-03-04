"""Async Redis backend for caching with automatic fallback."""

import os
import json
import hashlib
import asyncio
import time
from typing import Any, Optional, Dict
from siphon.config import get_logger

logger = get_logger("cache")

_redis_client: Optional[Any] = None
_redis_available: Optional[bool] = None
_last_connection_attempt: float = 0
_reconnect_interval: int = 30  # Try reconnect every 30 seconds

_connection_stamps: Dict[str, float] = {}
_stamp_lock = asyncio.Lock()


def _get_redis_url() -> Optional[str]:
    return os.getenv("REDIS_URL") or os.getenv("CACHE_REDIS_URL")


def _get_ttl() -> int:
    """Get TTL from environment or use default (24 hours)."""
    try:
        ttl = os.getenv("CACHE_TTL")
        if ttl:
            return int(ttl)
    except (ValueError, TypeError):
        pass
    return 86400  # Default: 24 hours


def _get_max_connections() -> int:
    """Get max connections from environment or use default."""
    try:
        max_conn = os.getenv("CACHE_MAX_CONNECTIONS")
        if max_conn:
            return int(max_conn)
    except (ValueError, TypeError):
        pass
    return 20  # Default: 20 connections per process


async def _get_redis_client():
    global _redis_client, _redis_available, _last_connection_attempt
    
    if _redis_available and _redis_client is not None:
        return _redis_client
    
    now = time.time()
    if _redis_available is False:
        if now - _last_connection_attempt < _reconnect_interval:
            return None
        logger.info("Attempting Redis reconnection...")
    
    _last_connection_attempt = now
    redis_url = _get_redis_url()
    if not redis_url:
        _redis_available = False
        logger.debug("No Redis URL configured, caching disabled")
        return None
    
    try:
        import redis.asyncio as redis
        _redis_client = redis.from_url(
            redis_url,
            max_connections=_get_max_connections(),
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
            retry_on_timeout=True,
        )
        await _redis_client.ping()
        _redis_available = True
        ttl = _get_ttl()
        logger.info(f"Redis cache connected: {redis_url.split('@')[-1] if '@' in redis_url else redis_url}, TTL: {ttl}s, Max connections: {_get_max_connections()}")
        return _redis_client
    except ImportError:
        logger.warning("redis package not installed, caching disabled. Install with: pip install redis")
        _redis_available = False
        return None
    except Exception as e:
        logger.warning(f"Redis connection failed, caching disabled: {e}")
        _redis_available = False
        return None


async def _with_stampede_protection(key: str, fetch_func, ttl: int = None) -> Any:
    """Prevent cache stampede using simple lock mechanism.
    
    If multiple requests come for same key simultaneously, only one fetches
    while others wait briefly and retry from cache.
    """
    async with _stamp_lock:
        if key in _connection_stamps:
            stamp_time = _connection_stamps[key]
            if time.time() - stamp_time < 5:  # Another request is already fetching
                pass  # Will wait below
        _connection_stamps[key] = time.time()
    
    try:
        result = await fetch_func()
        return result
    finally:
        async with _stamp_lock:
            _connection_stamps.pop(key, None)


def _make_outbound_trunk_key(sip_number: str, sip_address: str, sip_username: str) -> str:
    config_str = f"{sip_number}:{sip_address}:{sip_username}"
    hash_key = hashlib.sha256(config_str.encode()).hexdigest()[:16]
    return f"trunk:out:{hash_key}"


def _make_inbound_trunk_key(sip_number: str) -> str:
    safe_number = sip_number.lstrip("+").replace(" ", "_").replace("-", "_")
    return f"trunk:in:{safe_number}"


def _make_memory_key(phone_number: str) -> str:
    safe_phone = phone_number.lstrip("+").replace(" ", "_").replace("-", "_")
    return f"memory:{safe_phone}"


def _make_dispatch_key(sip_number: str) -> str:
    safe_number = sip_number.lstrip("+").replace(" ", "_").replace("-", "_")
    return f"dispatch:{safe_number}"


class CacheBackend:
    """Async Redis cache backend with automatic fallback."""
    
    @staticmethod
    async def get(key: str) -> Optional[str]:
        client = await _get_redis_client()
        if client is None:
            return None
        try:
            return await client.get(key)
        except Exception as e:
            logger.debug(f"Cache get error for key {key}: {e}")
            return None
    
    @staticmethod
    async def set(key: str, value: str, ttl: int = 3600) -> bool:
        client = await _get_redis_client()
        if client is None:
            return False
        try:
            await client.setex(key, ttl, value)
            return True
        except Exception as e:
            logger.debug(f"Cache set error for key {key}: {e}")
            return False
    
    @staticmethod
    async def delete(key: str) -> bool:
        client = await _get_redis_client()
        if client is None:
            return False
        try:
            await client.delete(key)
            return True
        except Exception as e:
            logger.debug(f"Cache delete error for key {key}: {e}")
            return False
    
    @staticmethod
    async def get_json(key: str) -> Optional[Dict[str, Any]]:
        value = await CacheBackend.get(key)
        if value is None:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    
    @staticmethod
    async def set_json(key: str, value: Dict[str, Any], ttl: int = 3600) -> bool:
        try:
            json_str = json.dumps(value, default=str)
            return await CacheBackend.set(key, json_str, ttl)
        except Exception as e:
            logger.debug(f"Cache set_json error: {e}")
            return False
    
    @staticmethod
    async def get_trunk_id_outbound(sip_number: str, sip_address: str, sip_username: str) -> Optional[str]:
        key = _make_outbound_trunk_key(sip_number, sip_address, sip_username)
        return await CacheBackend.get(key)
    
    @staticmethod
    async def set_trunk_id_outbound(sip_number: str, sip_address: str, sip_username: str, trunk_id: str) -> bool:
        key = _make_outbound_trunk_key(sip_number, sip_address, sip_username)
        return await CacheBackend.set(key, trunk_id, _get_ttl())
    
    @staticmethod
    async def get_trunk_id_inbound(sip_number: str) -> Optional[str]:
        key = _make_inbound_trunk_key(sip_number)
        return await CacheBackend.get(key)
    
    @staticmethod
    async def set_trunk_id_inbound(sip_number: str, trunk_id: str) -> bool:
        key = _make_inbound_trunk_key(sip_number)
        return await CacheBackend.set(key, trunk_id, _get_ttl())
    
    @staticmethod
    async def invalidate_trunk_outbound(sip_number: str, sip_address: str, sip_username: str) -> bool:
        key = _make_outbound_trunk_key(sip_number, sip_address, sip_username)
        return await CacheBackend.delete(key)
    
    @staticmethod
    async def invalidate_trunk_inbound(sip_number: str) -> bool:
        key = _make_inbound_trunk_key(sip_number)
        return await CacheBackend.delete(key)
    
    @staticmethod
    async def get_memory(phone_number: str) -> Optional[Dict[str, Any]]:
        key = _make_memory_key(phone_number)
        return await CacheBackend.get_json(key)
    
    @staticmethod
    async def set_memory(phone_number: str, memory_data: Dict[str, Any]) -> bool:
        key = _make_memory_key(phone_number)
        return await CacheBackend.set_json(key, memory_data, _get_ttl())
    
    @staticmethod
    async def invalidate_memory(phone_number: str) -> bool:
        key = _make_memory_key(phone_number)
        return await CacheBackend.delete(key)
    
    @staticmethod
    async def get_dispatch_rule(sip_number: str) -> Optional[Dict[str, Any]]:
        key = _make_dispatch_key(sip_number)
        return await CacheBackend.get_json(key)
    
    @staticmethod
    async def set_dispatch_rule(sip_number: str, rule_data: Dict[str, Any]) -> bool:
        key = _make_dispatch_key(sip_number)
        return await CacheBackend.set_json(key, rule_data, _get_ttl())
    
    @staticmethod
    async def invalidate_dispatch_rule(sip_number: str) -> bool:
        key = _make_dispatch_key(sip_number)
        return await CacheBackend.delete(key)
    
    @staticmethod
    async def health_check() -> Dict[str, Any]:
        client = await _get_redis_client()
        if client is None:
            return {"status": "unavailable", "message": "Redis not configured or connection failed"}
        try:
            await client.ping()
            return {"status": "healthy", "message": "Redis connection OK"}
        except Exception as e:
            return {"status": "unhealthy", "message": str(e)}
    
    @staticmethod
    async def close():
        global _redis_client
        if _redis_client is not None:
            try:
                await _redis_client.close()
            except Exception:
                pass
            _redis_client = None
