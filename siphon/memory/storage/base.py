"""Abstract base class for memory storage backends."""

from abc import ABC, abstractmethod
from typing import Optional
from siphon.memory.models import CallerMemory


class MemoryStore(ABC):
    """Abstract base class for call memory storage backends."""

    @abstractmethod
    async def get(self, phone_number: str) -> Optional[CallerMemory]:
        """Retrieve memory for a phone number.
        
        Args:
            phone_number: The phone number to look up
            
        Returns:
            CallerMemory if found, None otherwise
        """
        pass

    @abstractmethod
    async def save(self, phone_number: str, memory: CallerMemory) -> None:
        """Save memory for a phone number.
        
        Args:
            phone_number: The phone number to save for
            memory: The caller memory to save
        """
        pass

    @abstractmethod
    async def delete(self, phone_number: str) -> bool:
        """Delete memory for a phone number.
        
        Args:
            phone_number: The phone number to delete
            
        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    async def exists(self, phone_number: str) -> bool:
        """Check if memory exists for a phone number.
        
        Args:
            phone_number: The phone number to check
            
        Returns:
            True if memory exists, False otherwise
        """
        pass
