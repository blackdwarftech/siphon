"""SQL storage backend (PostgreSQL/MySQL) for call memory."""

import json
from typing import Optional, Dict, Any

from .base import MemoryStore


class SQLMemoryStore(MemoryStore):
    """SQL storage (PostgreSQL/MySQL) for call memory."""

    def __init__(self, url: str) -> None:
        try:
            from sqlalchemy import create_engine, text
        except ImportError as exc:
            raise RuntimeError("sqlalchemy is required for SQL memory storage") from exc

        # Handle MySQL URLs
        if url.startswith("mysql://") and not url.startswith("mysql+pymysql://"):
            url = "mysql+pymysql://" + url[len("mysql://") :]

        self._engine = create_engine(url)
        self._text = text

        # Create table if not exists
        with self._engine.begin() as conn:
            conn.execute(
                self._text(
                    """
                    CREATE TABLE IF NOT EXISTS caller_memories (
                        phone_number VARCHAR(50) PRIMARY KEY,
                        memory JSON NOT NULL,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )

    async def get(self, phone_number: str) -> Optional[Dict[str, Any]]:
        """Load memory from SQL database."""
        with self._engine.begin() as conn:
            result = conn.execute(
                self._text("SELECT memory FROM caller_memories WHERE phone_number = :phone"),
                {"phone": phone_number}
            )
            row = result.fetchone()
            if row:
                return json.loads(row[0])
            return None

    async def save(self, phone_number: str, memory: Dict[str, Any]) -> None:
        """Save memory to SQL database."""
        memory_json = json.dumps(memory)
        with self._engine.begin() as conn:
            conn.execute(
                self._text(
                    """
                    INSERT INTO caller_memories (phone_number, memory, updated_at)
                    VALUES (:phone, :memory, CURRENT_TIMESTAMP)
                    ON CONFLICT (phone_number) DO UPDATE SET
                        memory = EXCLUDED.memory,
                        updated_at = CURRENT_TIMESTAMP
                    """
                ),
                {"phone": phone_number, "memory": memory_json}
            )

    async def delete(self, phone_number: str) -> None:
        """Delete memory from SQL database."""
        with self._engine.begin() as conn:
            conn.execute(
                self._text("DELETE FROM caller_memories WHERE phone_number = :phone"),
                {"phone": phone_number}
            )

    async def exists(self, phone_number: str) -> bool:
        """Check if memory exists in SQL database."""
        with self._engine.begin() as conn:
            result = conn.execute(
                self._text("SELECT 1 FROM caller_memories WHERE phone_number = :phone"),
                {"phone": phone_number}
            )
            return result.fetchone() is not None
