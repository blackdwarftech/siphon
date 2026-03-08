"""SQL storage backend (PostgreSQL/MySQL) for call memory."""

import json
from typing import Optional
from urllib.parse import urlparse, parse_qs

from .base import MemoryStore
from siphon.memory.models import CallerMemory
from siphon.config import get_logger

logger = get_logger("calling-agent")


class SQLMemoryStore(MemoryStore):
    """SQL storage (PostgreSQL/MySQL) for call memory."""

    def __init__(self, url: str) -> None:
        try:
            from sqlalchemy.ext.asyncio import create_async_engine
            from sqlalchemy import text
        except ImportError as exc:
            raise RuntimeError("sqlalchemy.ext.asyncio is required for SQL memory storage") from exc

        # Parse URL to extract components and query params
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        
        # Determine database type
        url_lower = url.lower()
        self._is_mysql = url_lower.startswith('mysql')
        self._is_postgres = url_lower.startswith('postgres')
        
        # Rebuild URL without query params for SQLAlchemy
        clean_url = f"{parsed.scheme}://"
        if parsed.username:
            clean_url += parsed.username
            if parsed.password:
                clean_url += f":{parsed.password}"
            clean_url += "@"
        if parsed.hostname:
            clean_url += parsed.hostname
        elif "sqlite" not in parsed.scheme:
            clean_url += "localhost"
        if parsed.port:
            clean_url += f":{parsed.port}"
        clean_url += parsed.path
        
        # Handle async scheme conversions
        if self._is_mysql:
            scheme = clean_url.split("://")[0]
            clean_url = clean_url.replace(f"{scheme}://", "mysql+aiomysql://", 1)
        elif self._is_postgres:
            scheme = clean_url.split("://")[0]
            clean_url = clean_url.replace(f"{scheme}://", "postgresql+asyncpg://", 1)
        
        # Build connection arguments
        connect_args = {}
        
        # Handle SSL configuration and Timeouts
        if self._is_mysql:
            # MySQL uses 'ssl-mode' or 'ssl' parameter
            ssl_mode = query_params.get('ssl-mode', [''])[0].lower()
            if ssl_mode in ['required', 'preferred', 'verify-ca', 'verify-identity']:
                # Enable SSL for MySQL
                connect_args['ssl'] = True
            connect_args['connect_timeout'] = 2
        elif self._is_postgres:
            # PostgreSQL uses 'sslmode' parameter
            ssl_mode = query_params.get('sslmode', [''])[0].lower()
            if ssl_mode in ['require', 'prefer', 'verify-ca', 'verify-full']:
                # Enable SSL for PostgreSQL
                connect_args['ssl'] = True
            connect_args['timeout'] = 2
            connect_args['command_timeout'] = 2
        
        self._engine = create_async_engine(clean_url, connect_args=connect_args)
        self._text = text
        self._initialized = False

    async def _ensure_initialized(self) -> None:
        """Create the caller_memories table with dialect-specific syntax if it doesn't exist."""
        if self._initialized:
            return

        if self._is_mysql:
            # MySQL syntax
            create_sql = """
                CREATE TABLE IF NOT EXISTS caller_memories (
                    phone_number VARCHAR(50) PRIMARY KEY,
                    memory JSON NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        ON UPDATE CURRENT_TIMESTAMP
                )
            """
        else:
            # PostgreSQL syntax
            create_sql = """
                CREATE TABLE IF NOT EXISTS caller_memories (
                    phone_number VARCHAR(50) PRIMARY KEY,
                    memory JSONB NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
        
        try:
            async with self._engine.begin() as conn:
                await conn.execute(self._text(create_sql))
            self._initialized = True
        except Exception as e:
            logger.error(f"SQL init table failed (db might be unreachable): {e}")

    async def get(self, phone_number: str) -> Optional[CallerMemory]:
        """Load memory from SQL database."""
        await self._ensure_initialized()
        try:
            async with self._engine.begin() as conn:
                result = await conn.execute(
                    self._text("SELECT memory FROM caller_memories WHERE phone_number = :phone"),
                    {"phone": phone_number}
                )
                row = result.fetchone()
                if row:
                    # PostgreSQL JSON column returns dict directly, MySQL returns string
                    data = row[0]
                    if isinstance(data, str):
                        data = json.loads(data)
                    memory = CallerMemory.model_validate(data)
                    logger.info(f"Loaded memory from SQL for {phone_number}: {memory.total_calls} calls, {len(memory.summaries)} summaries")
                    return memory
            logger.debug(f"No memory found in SQL for {phone_number}")
            return None
        except Exception as e:
            logger.error(f"SQL get failed for {phone_number}: {e}")
            return None

    async def save(self, phone_number: str, memory: CallerMemory) -> None:
        """Save memory to SQL database."""
        await self._ensure_initialized()
        
        try:
            # Convert CallerMemory to dict
            memory_dict = memory.model_dump()
            # Serialize to JSON string for storage
            memory_json = json.dumps(memory_dict, default=str)
            
            async with self._engine.begin() as conn:
                if self._is_mysql:
                    # MySQL syntax: ON DUPLICATE KEY UPDATE
                    await conn.execute(
                        self._text(
                            """
                            INSERT INTO caller_memories (phone_number, memory, updated_at)
                            VALUES (:phone, :memory, CURRENT_TIMESTAMP)
                            ON DUPLICATE KEY UPDATE
                                memory = VALUES(memory),
                                updated_at = CURRENT_TIMESTAMP
                            """
                        ),
                        {"phone": phone_number, "memory": memory_json}
                    )
                else:
                    # PostgreSQL syntax: ON CONFLICT
                    await conn.execute(
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
            logger.info(f"Saved memory to SQL for {phone_number}: {memory.total_calls} calls, {len(memory.summaries)} summaries")
        except Exception as e:
            logger.error(f"SQL save failed for {phone_number}: {e}")

    async def delete(self, phone_number: str) -> bool:
        """Delete memory from SQL database."""
        await self._ensure_initialized()
        try:
            async with self._engine.begin() as conn:
                result = await conn.execute(
                    self._text("DELETE FROM caller_memories WHERE phone_number = :phone"),
                    {"phone": phone_number}
                )
                return result.rowcount > 0
        except Exception as e:
            logger.error(f"SQL delete failed for {phone_number}: {e}")
            return False

    async def exists(self, phone_number: str) -> bool:
        """Check if memory exists in SQL database."""
        await self._ensure_initialized()
        try:
            async with self._engine.begin() as conn:
                result = await conn.execute(
                    self._text("SELECT 1 FROM caller_memories WHERE phone_number = :phone"),
                    {"phone": phone_number}
                )
                return result.fetchone() is not None
        except Exception as e:
            logger.error(f"SQL exists check failed for {phone_number}: {e}")
            return False
