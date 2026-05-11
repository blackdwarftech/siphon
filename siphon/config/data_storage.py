import asyncio
import copy
import json
import os
import re
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

import boto3
from botocore.config import Config

from .logging_config import get_logger
from .s3_utils import ensure_s3_bucket_sync, get_s3_config
from .timezone_utils import get_timezone

logger = get_logger("calling-agent")

MYSQL_PREFIX = "mysql://"
MYSQL_PYMYSQL_PREFIX = "mysql+pymysql://"


class BaseStore:
    backend_name = "base"

    def __init__(self, kind: str = "metadata") -> None:
        # kind is a logical namespace, e.g. "metadata" or "transcription",
        # used for table names, Redis keys, file prefixes, etc.
        self._kind = kind

    async def save(
        self, payload: dict, room_name: str, s3_key: Optional[str] = None
    ) -> None:  # pragma: no cover - interface
        raise NotImplementedError


class LocalStore(BaseStore):
    backend_name = "local"

    def __init__(self, base_folder: str, kind: str = "metadata") -> None:
        super().__init__(kind)
        self.base_folder = base_folder or "Call_Metadata"

    async def save(
        self, payload: dict, room_name: str, s3_key: Optional[str] = None
    ) -> None:
        tz = get_timezone()
        now = datetime.now(tz) if tz is not None else datetime.now()
        timestamp = now.strftime("%d-%m-%Y-%I-%M-%p")
        safe_room_name = re.sub(r'[^\w\-_.]', '_', room_name)
        folder = os.path.join(self.base_folder, safe_room_name, timestamp)
        os.makedirs(folder, exist_ok=True)
        filename = f"call_{self._kind}_{safe_room_name}_{timestamp}.json"
        path = os.path.join(folder, filename)
        
        try:
            import aiofiles
            async with aiofiles.open(path, "w", encoding="utf-8") as f:
                content = json.dumps(payload, indent=4, ensure_ascii=False)
                await f.write(content)
        except ImportError:
            import asyncio
            def _write_sync():
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=4, ensure_ascii=False)
            await asyncio.to_thread(_write_sync)
            
        logger.info(f"Call data saved to {path}")


class S3Store(BaseStore):
    backend_name = "s3"

    def __init__(self, kind: str = "metadata") -> None:
        super().__init__(kind)
        self.config = self._get_s3_config()

    def _get_s3_config(self) -> dict:
        return get_s3_config()

    async def save(
        self, payload: dict, room_name: str, s3_key: Optional[str] = None
    ) -> None:
        tz = get_timezone()
        now = datetime.now(tz) if tz is not None else datetime.now()
        timestamp = now.strftime("%d-%m-%Y-%I-%M-%p")
        safe_room_name = re.sub(r'[^\w\-_.]', '_', room_name)
        if s3_key:
            base = os.path.dirname(s3_key)
        else:
            base = f"{safe_room_name}/{timestamp}"
        filename = f"call_{self._kind}_{safe_room_name}_{timestamp}.json"
        key = f"{base}/{filename}"
        session = boto3.session.Session(
            aws_access_key_id=self.config["access_key"],
            aws_secret_access_key=self.config["secret"],
            region_name=self.config["region"],
        )
        client_kwargs: dict = {}
        if self.config["endpoint"]:
            client_kwargs["endpoint_url"] = self.config["endpoint"]
        if self.config["force_path_style"]:
            client_kwargs["config"] = Config(s3={"addressing_style": "path"})
        s3_client = session.client("s3", **client_kwargs)
        ensure_s3_bucket_sync(s3_client, self.config["bucket"], self.config["region"])
        # Use ensure_ascii=False so non-ASCII text is stored as UTF-8
        # characters instead of escaped sequences.
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        
        put_kwargs = {
            "Bucket": self.config["bucket"],
            "Key": key,
            "Body": body,
            "ContentType": "application/json",
        }
        
        expected_owner = os.getenv("AWS_S3_EXPECTED_BUCKET_OWNER")
        if expected_owner:
            put_kwargs["ExpectedBucketOwner"] = expected_owner
        
        def _put_sync():
            s3_client.put_object(**put_kwargs)
        
        await asyncio.to_thread(_put_sync)
        logger.info(
            f"Call data saved to s3://{self.config['bucket']}/{key}"
        )


class MongoStore(BaseStore):
    backend_name = "mongodb"

    def __init__(self, url: str, kind: str = "metadata") -> None:
        super().__init__(kind)
        try:
            from motor.motor_asyncio import AsyncIOMotorClient  # type: ignore
            import certifi
        except ImportError as exc:
            raise RuntimeError("motor and certifi are required for MongoDB metadata storage") from exc
        parsed = urlparse(url)
        db_name = parsed.path.lstrip("/") or "call_metadata"
        # Use certifi's CA bundle for reliable TLS across environments,
        # and disable OCSP endpoint checks to avoid OpenSSL 3.x strictness issues.
        self.client = AsyncIOMotorClient(
            url,
            tlsCAFile=certifi.where(),
            tlsDisableOCSPEndpointCheck=True,
        )
        collection_name = f"call_{self._kind}"
        self.collection = self.client[db_name][collection_name]

    async def save(
        self, payload: dict, room_name: str, s3_key: Optional[str] = None
    ) -> None:
        document = copy.deepcopy(payload)
        if "room_name" not in document:
            document["room_name"] = room_name
        await self.collection.insert_one(document)
        logger.info("Call data saved to MongoDB")

    def close(self) -> None:
        if self.client:
            self.client.close()


class RedisStore(BaseStore):
    backend_name = "redis"

    def __init__(self, url: str, kind: str = "metadata") -> None:
        super().__init__(kind)
        try:
            import redis  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "redis is required for Redis metadata storage"
            ) from exc
        # Using from_url preserves DB index, password, TLS, etc.
        self._client = redis.from_url(url)

    async def save(
        self, payload: dict, room_name: str, s3_key: Optional[str] = None
    ) -> None:
        # Preserve non-ASCII characters (e.g. Hindi) as-is
        payload_json = json.dumps(payload, ensure_ascii=False)
        key = f"call_{self._kind}:{room_name}"
        # Append to a list so multiple calls per room are retained.
        await asyncio.to_thread(self._client.rpush, key, payload_json)
        logger.info("Call data saved to Redis", extra={"key": key})


class SqlStore(BaseStore):
    backend_name = "sql"

    def __init__(self, url: str, kind: str = "metadata") -> None:
        super().__init__(kind)
        try:
            from sqlalchemy import create_engine, text  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "sqlalchemy is required for SQL metadata storage"
            ) from exc
        # If user provided a generic MySQL URL (mysql://...), transparently
        # map it to the PyMySQL driver so we don't require the MySQLdb module.
        if url.startswith(MYSQL_PREFIX) and not url.startswith(MYSQL_PYMYSQL_PREFIX):
            url = MYSQL_PYMYSQL_PREFIX + url[len(MYSQL_PREFIX) :]

        self._engine = create_engine(url)
        self._text = text
        safe_kind = re.sub(r'[^a-zA-Z0-9_]', '_', self._kind)
        self._table_name = f"call_{safe_kind}"
        self._table_created = False

    def _ensure_table(self) -> None:
        if self._table_created:
            return
        with self._engine.begin() as conn:
            conn.execute(
                self._text(
                    "CREATE TABLE IF NOT EXISTS {} (room_name TEXT, payload TEXT)".format(self._table_name)
                )
            )
        self._table_created = True

    async def save(
        self, payload: dict, room_name: str, s3_key: Optional[str] = None
    ) -> None:
        await asyncio.to_thread(self._ensure_table)
        payload_json = json.dumps(payload)
        
        def _save_sync():
            with self._engine.begin() as conn:
                conn.execute(
                    self._text(
                        "INSERT INTO {} (room_name, payload) VALUES (:room_name, :payload)".format(self._table_name)
                    ),
                    {"room_name": room_name, "payload": payload_json},
                )
        
        await asyncio.to_thread(_save_sync)
        logger.info("Call data saved to SQL database")


_data_store_cache: dict = {}

def get_data_store(location: Optional[str], kind: str = "metadata") -> BaseStore:
    cache_key = (location, kind)
    if cache_key in _data_store_cache:
        return _data_store_cache[cache_key]
    
    if not location:
        store = LocalStore("Call_Metadata", kind=kind)
    else:
        value = location.strip()
        if not value:
            store = LocalStore("Call_Metadata", kind=kind)
        elif value.lower() == "s3":
            store = S3Store(kind=kind)
        elif value.startswith("redis://") or value.startswith("rediss://"):
            store = RedisStore(value, kind=kind)
        elif value.startswith("mongodb://") or value.startswith("mongodb+srv://"):
            store = MongoStore(value, kind=kind)
        elif value.startswith("postgres://") or value.startswith("postgresql://"):
            store = SqlStore(value, kind=kind)
        elif value.startswith(MYSQL_PREFIX) or value.startswith(MYSQL_PYMYSQL_PREFIX):
            store = SqlStore(value, kind=kind)
        else:
            store = LocalStore(value, kind=kind)
    
    _data_store_cache[cache_key] = store
    return store
