import json
import os
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

import boto3
from botocore.config import Config

from .logging_config import get_logger
from .timezone_utils import get_timezone


logger = get_logger("calling-agent")


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
        safe_room_name = room_name.replace(" ", "_")
        folder = os.path.join(self.base_folder, safe_room_name, timestamp)
        os.makedirs(folder, exist_ok=True)
        filename = f"call_{self._kind}_{safe_room_name}_{timestamp}.json"
        path = os.path.join(folder, filename)
        with open(path, "w", encoding="utf-8") as f:
            # ensure_ascii=False keeps non-ASCII characters (e.g. Hindi)
            # as readable text instead of \uXXXX escapes.
            json.dump(payload, f, indent=4, ensure_ascii=False)
        logger.info(f"Call data saved to {path}")


class S3Store(BaseStore):
    backend_name = "s3"

    def __init__(self, kind: str = "metadata") -> None:
        super().__init__(kind)
        self.config = self._get_s3_config()

    def _get_s3_config(self) -> dict:
        s3_endpoint = os.getenv("AWS_S3_ENDPOINT")
        s3_access_key = (
            os.getenv("AWS_S3_ACCESS_KEY_ID")
            or os.getenv("AWS_ACCESS_KEY_ID")
            or os.getenv("MINIO_ACCESS_KEY")
        )
        s3_secret_key = (
            os.getenv("AWS_S3_SECRET_ACCESS_KEY")
            or os.getenv("AWS_SECRET_ACCESS_KEY")
            or os.getenv("MINIO_SECRET_KEY")
        )
        s3_bucket = os.getenv("AWS_S3_BUCKET") or os.getenv("MINIO_BUCKET")
        s3_region = os.getenv("AWS_S3_REGION", "us-east-1")
        s3_force_path_style = (
            os.getenv("AWS_S3_FORCE_PATH_STYLE", "false").lower() == "true"
        )
        if not all([s3_access_key, s3_secret_key, s3_bucket]):
            raise Exception(
                "S3/MinIO credentials missing. Set AWS_S3_ACCESS_KEY_ID / MINIO_ACCESS_KEY, "
                "AWS_S3_SECRET_ACCESS_KEY / MINIO_SECRET_KEY and AWS_S3_BUCKET / MINIO_BUCKET"
            )
        return {
            "access_key": s3_access_key,
            "secret": s3_secret_key,
            "bucket": s3_bucket,
            "region": s3_region,
            "endpoint": s3_endpoint,
            "force_path_style": s3_force_path_style,
        }

    async def save(
        self, payload: dict, room_name: str, s3_key: Optional[str] = None
    ) -> None:
        tz = get_timezone()
        now = datetime.now(tz) if tz is not None else datetime.now()
        timestamp = now.strftime("%d-%m-%Y-%I-%M-%p")
        safe_room_name = room_name.replace(" ", "_")
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
        # Use ensure_ascii=False so non-ASCII text is stored as UTF-8
        # characters instead of escaped sequences.
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        s3_client.put_object(
            Bucket=self.config["bucket"],
            Key=key,
            Body=body,
            ContentType="application/json",
        )
        logger.info(
            f"Call data saved to s3://{self.config['bucket']}/{key}"
        )


class MongoStore(BaseStore):
    backend_name = "mongodb"

    def __init__(self, url: str, kind: str = "metadata") -> None:
        super().__init__(kind)
        try:
            from pymongo import MongoClient  # type: ignore
        except ImportError as exc:
            raise RuntimeError("pymongo is required for MongoDB metadata storage") from exc
        parsed = urlparse(url)
        db_name = parsed.path.lstrip("/") or "call_metadata"
        client = MongoClient(url)
        collection_name = f"call_{self._kind}"
        self.collection = client[db_name][collection_name]

    async def save(
        self, payload: dict, room_name: str, s3_key: Optional[str] = None
    ) -> None:
        document = dict(payload)
        if "room_name" not in document:
            document["room_name"] = room_name
        self.collection.insert_one(document)
        logger.info("Call data saved to MongoDB")


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
        self._client.rpush(key, payload_json)
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
        if url.startswith("mysql://") and not url.startswith("mysql+pymysql://"):
            url = "mysql+pymysql://" + url[len("mysql://") :]

        self._engine = create_engine(url)
        self._text = text
        self._table_name = f"call_{self._kind}"
        with self._engine.begin() as conn:
            conn.execute(
                self._text(
                    f"CREATE TABLE IF NOT EXISTS {self._table_name} (room_name TEXT, payload TEXT)"
                )
            )

    async def save(
        self, payload: dict, room_name: str, s3_key: Optional[str] = None
    ) -> None:
        payload_json = json.dumps(payload)
        with self._engine.begin() as conn:
            conn.execute(
                self._text(
                    f"INSERT INTO {self._table_name} (room_name, payload) VALUES (:room_name, :payload)"
                ),
                {"room_name": room_name, "payload": payload_json},
            )
        logger.info("Call data saved to SQL database")


def get_data_store(location: Optional[str], kind: str = "metadata") -> BaseStore:
    if not location:
        return LocalStore("Call_Metadata", kind=kind)
    value = location.strip()
    if not value:
        return LocalStore("Call_Metadata", kind=kind)
    lower = value.lower()
    if lower == "s3":
        return S3Store(kind=kind)
    if value.startswith("redis://") or value.startswith("rediss://"):
        return RedisStore(value, kind=kind)
    if value.startswith("mongodb://") or value.startswith("mongodb+srv://"):
        return MongoStore(value, kind=kind)
    if value.startswith("postgres://") or value.startswith("postgresql://"):
        return SqlStore(value, kind=kind)
    if value.startswith("mysql://") or value.startswith("mysql+pymysql://"):
        return SqlStore(value, kind=kind)
    return LocalStore(value, kind=kind)
