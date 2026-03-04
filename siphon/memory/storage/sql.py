"""SQL storage backend (PostgreSQL/MySQL) for call memory."""

import json
from typing import Optional
from urllib.parse import urlparse, parse_qs

from .base import MemoryStore
from siphon.memory.models import CallerMemory


class SQLMemoryStore(MemoryStore):
    """SQL storage (PostgreSQL/MySQL) for call memory."""

    def __init__(self, url: str) -> None:
        try:
            from sqlalchemy import create_engine, text
        except ImportError as exc:
            raise RuntimeError("sqlalchemy is required for SQL memory storage") from exc

        # Parse URL to extract components and query params
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        
        # Determine database type
        url_lower = url.lower()
        self._is_mysql = url_lower.startswith('mysql://') or url_lower.startswith('mysql+pymysql://')
        self._is_postgres = url_lower.startswith('postgres://') or url_lower.startswith('postgresql://')
        
        # Rebuild URL without query params for SQLAlchemy
        clean_url = f"{parsed.scheme}://"
        if parsed.username:
            clean_url += parsed.username
            if parsed.password:
                clean_url += f":{parsed.password}"
            clean_url += "@"
        clean_url += parsed.hostname or "localhost"
        if parsed.port:
            clean_url += f":{parsed.port}"
        clean_url += parsed.path
        
        # Handle MySQL URLs - convert to mysql+pymysql
        if clean_url.startswith("mysql://") and not clean_url.startswith("mysql+pymysql://"):
            clean_url = "mysql+pymysql://" + clean_url[len("mysql://"):]
        
        # Build connection arguments
        connect_args = {}
        
        # Handle SSL configuration
        if self._is_mysql:
            # MySQL uses 'ssl-mode' or 'ssl' parameter
            ssl_mode = query_params.get('ssl-mode', [''])[0].lower()
            if ssl_mode in ['required', 'preferred', 'verify-ca', 'verify-identity']:
                # Enable SSL for MySQL
                # Use ssl_disabled=False to enable SSL without ca_cert requirement
                connect_args['ssl_disabled'] = False
        elif self._is_postgres:
            # PostgreSQL uses 'sslmode' parameter
            ssl_mode = query_params.get('sslmode', [''])[0].lower()
            if ssl_mode in ['require', 'prefer', 'verify-ca', 'verify-full']:
                # Enable SSL for PostgreSQL
                connect_args['sslmode'] = ssl_mode
        
        self._engine = create_engine(clean_url, connect_args=connect_args if connect_args else {})
        self._text = text

        # Create table if not exists (use appropriate syntax for each DB)
        self._create_table()

    def _create_table(self) -> None:
        """Create the caller_memories table with dialect-specific syntax."""
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
        
        with self._engine.begin() as conn:
            conn.execute(self._text(create_sql))

    async def get(self, phone_number: str) -> Optional[CallerMemory]:
        """Load memory from SQL database."""
        with self._engine.begin() as conn:
            result = conn.execute(
                self._text("SELECT memory FROM caller_memories WHERE phone_number = :phone"),
                {"phone": phone_number}
            )
            row = result.fetchone()
            if row:
                # PostgreSQL JSON column returns dict directly, MySQL returns string
                data = row[0]
                if isinstance(data, str):
                    data = json.loads(data)
                return CallerMemory.model_validate(data)
            return None

    async def save(self, phone_number: str, memory: CallerMemory) -> None:
        """Save memory to SQL database."""
        from siphon.config import get_logger
        logger = get_logger("calling-agent")
        
        try:
            # Convert CallerMemory to dict
            memory_dict = memory.model_dump()
            # Serialize to JSON string for storage
            memory_json = json.dumps(memory_dict, default=str)
            
            with self._engine.begin() as conn:
                if self._is_mysql:
                    # MySQL syntax: ON DUPLICATE KEY UPDATE
                    conn.execute(
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
            logger.debug(f"Memory saved to SQL database for {phone_number}")
        except Exception as e:
            logger.error(f"Error saving memory to SQL database: {e}")
            raise

    async def delete(self, phone_number: str) -> bool:
        """Delete memory from SQL database."""
        with self._engine.begin() as conn:
            result = conn.execute(
                self._text("DELETE FROM caller_memories WHERE phone_number = :phone"),
                {"phone": phone_number}
            )
            return result.rowcount > 0

    async def exists(self, phone_number: str) -> bool:
        """Check if memory exists in SQL database."""
        with self._engine.begin() as conn:
            result = conn.execute(
                self._text("SELECT 1 FROM caller_memories WHERE phone_number = :phone"),
                {"phone": phone_number}
            )
            return result.fetchone() is not None
