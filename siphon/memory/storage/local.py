"""Local JSON file storage for call memory."""

import json
import os
from typing import Optional
from siphon.memory.storage.base import MemoryStore
from siphon.memory.models import CallerMemory
from siphon.config import get_logger

logger = get_logger("calling-agent")


class LocalMemoryStore(MemoryStore):
    """Local JSON file storage for call memory.
    
    Stores one JSON file per phone number:
    Call_Memory/
    ├── +1234567890.json
    ├── +1987654321.json
    """

    def __init__(self, base_folder: str = "Call_Memory") -> None:
        self.base_folder = base_folder
        os.makedirs(self.base_folder, exist_ok=True)

    def _get_file_path(self, phone_number: str) -> str:
        """Get file path for a phone number."""
        # Sanitize phone number for filename
        safe_phone = phone_number.lstrip("+").replace(" ", "_").replace("-", "_")
        return os.path.join(self.base_folder, f"{safe_phone}.json")

    async def get(self, phone_number: str) -> Optional[CallerMemory]:
        """Load memory from JSON file."""
        try:
            file_path = self._get_file_path(phone_number)
            if not os.path.exists(file_path):
                return None
            
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            return CallerMemory.model_validate(data)
        except Exception as e:
            logger.error(f"Error loading memory from {file_path}: {e}")
            return None

    async def save(self, phone_number: str, memory: CallerMemory) -> None:
        """Save memory to JSON file."""
        try:
            file_path = self._get_file_path(phone_number)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(memory.model_dump(), f, indent=2, ensure_ascii=False, default=str)
            logger.info(f"Call memory saved to {file_path}")
        except Exception as e:
            logger.error(f"Error saving memory to {file_path}: {e}")

    async def delete(self, phone_number: str) -> bool:
        """Delete memory file."""
        try:
            file_path = self._get_file_path(phone_number)
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting memory for {phone_number}: {e}")
            return False

    async def exists(self, phone_number: str) -> bool:
        """Check if memory exists."""
        file_path = self._get_file_path(phone_number)
        return os.path.exists(file_path)
