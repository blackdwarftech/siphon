"""S3/MinIO utility helpers for lazy bucket creation."""

import os
from typing import Dict, Any
from botocore.exceptions import ClientError
from .logging_config import get_logger

logger = get_logger("calling-agent")


def get_s3_config() -> Dict[str, Any]:
    """Return S3/MinIO configuration derived from environment variables.

    Checks the following environment variables (in order of precedence):
      - AWS_S3_ACCESS_KEY_ID / AWS_ACCESS_KEY_ID / MINIO_ACCESS_KEY
      - AWS_S3_SECRET_ACCESS_KEY / AWS_SECRET_ACCESS_KEY / MINIO_SECRET_KEY
      - AWS_S3_BUCKET / MINIO_BUCKET
      - AWS_S3_ENDPOINT (optional, for MinIO)
      - AWS_S3_REGION (default: us-east-1)
      - AWS_S3_FORCE_PATH_STYLE (default: false)

    Raises:
        RuntimeError: If required credentials (access_key, secret_key, bucket) are missing.
    """
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
        raise RuntimeError(
            "S3/MinIO credentials missing. Set:\n"
            "  AWS_S3_ACCESS_KEY_ID / MINIO_ACCESS_KEY\n"
            "  AWS_S3_SECRET_ACCESS_KEY / MINIO_SECRET_KEY\n"
            "  AWS_S3_BUCKET / MINIO_BUCKET"
        )

    return {
        "access_key": s3_access_key,
        "secret": s3_secret_key,
        "bucket": s3_bucket,
        "region": s3_region,
        "endpoint": s3_endpoint,
        "force_path_style": s3_force_path_style,
    }


def ensure_s3_bucket_sync(client, bucket: str, region: str) -> bool:
    """Ensure an S3/MinIO bucket exists, creating it lazily if necessary.

    This is a *best-effort* helper: if the bucket cannot be created (e.g.
    permissions), a warning is logged and execution continues so that the
    caller can still attempt the operation (the bucket may already exist).
    """
    try:
        client.head_bucket(Bucket=bucket)
        logger.debug(f"S3 bucket '{bucket}' already exists")
        return True
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code in ("404", "NoSuchBucket", "NotFound"):
            try:
                create_kwargs: dict = {"Bucket": bucket}
                if region != "us-east-1":
                    create_kwargs["CreateBucketConfiguration"] = {
                        "LocationConstraint": region
                    }
                client.create_bucket(**create_kwargs)
                logger.info(f"Created S3 bucket '{bucket}' in region '{region}'")
                return True
            except ClientError as create_err:
                create_code = create_err.response.get("Error", {}).get("Code", "")
                if create_code == "BucketAlreadyExists":
                    return True
                logger.warning(
                    f"Failed to create S3 bucket '{bucket}': {create_err}. "
                    "Continuing assuming bucket already exists or will be created by operator."
                )
                return False
        else:
            logger.warning(
                f"Could not verify S3 bucket '{bucket}' existence (error: {error_code}): {e}. "
                "Continuing assuming bucket exists."
            )
            return False
    except Exception as e:
        logger.warning(
            f"Unexpected error checking S3 bucket '{bucket}': {e}. "
            "Continuing assuming bucket exists."
        )
        return False


async def ensure_s3_bucket_async(client, bucket: str, region: str) -> bool:
    """Async variant of :func:`ensure_s3_bucket_sync`."""
    try:
        await client.head_bucket(Bucket=bucket)
        logger.debug(f"S3 bucket '{bucket}' already exists")
        return True
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code in ("404", "NoSuchBucket", "NotFound"):
            try:
                create_kwargs: dict = {"Bucket": bucket}
                if region != "us-east-1":
                    create_kwargs["CreateBucketConfiguration"] = {
                        "LocationConstraint": region
                    }
                await client.create_bucket(**create_kwargs)
                logger.info(f"Created S3 bucket '{bucket}' in region '{region}'")
                return True
            except ClientError as create_err:
                create_code = create_err.response.get("Error", {}).get("Code", "")
                if create_code == "BucketAlreadyExists":
                    return True
                logger.warning(
                    f"Failed to create S3 bucket '{bucket}': {create_err}. "
                    "Continuing assuming bucket already exists or will be created by operator."
                )
                return False
        else:
            logger.warning(
                f"Could not verify S3 bucket '{bucket}' existence (error: {error_code}): {e}. "
                "Continuing assuming bucket exists."
            )
            return False
    except Exception as e:
        logger.warning(
            f"Unexpected error checking S3 bucket '{bucket}': {e}. "
            "Continuing assuming bucket exists."
        )
        return False
