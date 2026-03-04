"""Cache Service - Centralized caching for SIP trunks and memory."""

from typing import Any, Optional, Dict
from siphon.cache.backend import CacheBackend
from siphon.config import get_logger

logger = get_logger("cache")


class CacheService:
    """Centralized caching service for SIPHON.
    
    Provides caching for:
    - Outbound SIP trunk IDs (by credentials)
    - Inbound SIP trunk IDs (by phone number)
    - Caller memory (by phone number)
    - Dispatch rules (by phone number)
    
    All methods automatically fallback to None if Redis is unavailable.
    """
    
    _instance: Optional["CacheService"] = None
    
    def __new__(cls) -> "CacheService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def get_trunk_id_outbound(
        self, 
        sip_number: str, 
        sip_address: str, 
        sip_username: str
    ) -> Optional[str]:
        """Get cached outbound trunk ID by SIP credentials."""
        return await CacheBackend.get_trunk_id_outbound(
            sip_number, sip_address, sip_username
        )
    
    async def set_trunk_id_outbound(
        self, 
        sip_number: str, 
        sip_address: str, 
        sip_username: str, 
        trunk_id: str
    ) -> bool:
        """Cache outbound trunk ID."""
        result = await CacheBackend.set_trunk_id_outbound(
            sip_number, sip_address, sip_username, trunk_id
        )
        if result:
            logger.debug(f"Cached outbound trunk {trunk_id} for {sip_number}")
        return result
    
    async def get_trunk_id_inbound(self, sip_number: str) -> Optional[str]:
        """Get cached inbound trunk ID by phone number."""
        return await CacheBackend.get_trunk_id_inbound(sip_number)
    
    async def set_trunk_id_inbound(self, sip_number: str, trunk_id: str) -> bool:
        """Cache inbound trunk ID."""
        result = await CacheBackend.set_trunk_id_inbound(sip_number, trunk_id)
        if result:
            logger.debug(f"Cached inbound trunk {trunk_id} for {sip_number}")
        return result
    
    async def invalidate_trunk_outbound(
        self, 
        sip_number: str, 
        sip_address: str, 
        sip_username: str
    ) -> bool:
        """Invalidate cached outbound trunk ID."""
        return await CacheBackend.invalidate_trunk_outbound(
            sip_number, sip_address, sip_username
        )
    
    async def invalidate_trunk_inbound(self, sip_number: str) -> bool:
        """Invalidate cached inbound trunk ID."""
        return await CacheBackend.invalidate_trunk_inbound(sip_number)
    
    async def get_memory(self, phone_number: str) -> Optional[Dict[str, Any]]:
        """Get cached caller memory."""
        return await CacheBackend.get_memory(phone_number)
    
    async def set_memory(self, phone_number: str, memory_data: Dict[str, Any]) -> bool:
        """Cache caller memory."""
        result = await CacheBackend.set_memory(phone_number, memory_data)
        if result:
            logger.debug(f"Cached memory for {phone_number}")
        return result
    
    async def invalidate_memory(self, phone_number: str) -> bool:
        """Invalidate cached caller memory."""
        return await CacheBackend.invalidate_memory(phone_number)
    
    async def get_dispatch_rule(self, sip_number: str) -> Optional[Dict[str, Any]]:
        """Get cached dispatch rule by phone number."""
        return await CacheBackend.get_dispatch_rule(sip_number)
    
    async def set_dispatch_rule(self, sip_number: str, rule_data: Dict[str, Any]) -> bool:
        """Cache dispatch rule."""
        return await CacheBackend.set_dispatch_rule(sip_number, rule_data)
    
    async def invalidate_dispatch_rule(self, sip_number: str) -> bool:
        """Invalidate cached dispatch rule."""
        return await CacheBackend.invalidate_dispatch_rule(sip_number)
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Redis connection health."""
        return await CacheBackend.health_check()
    
    async def close(self):
        """Close Redis connection."""
        await CacheBackend.close()


_cache_service: Optional[CacheService] = None


def get_cache_service() -> CacheService:
    """Get the singleton CacheService instance."""
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
    return _cache_service
