"""S3 storage service for paper source files.

Uses boto3 (synchronous) wrapped in ``asyncio.to_thread`` so upload/
download calls don't block the event loop. The client is lazily
constructed and cached (``lru_cache``) rather than built at import time,
since credentials may not be configured until runtime and importing this
module must never require AWS to be reachable.
"""

import asyncio
from functools import lru_cache
from typing import Any

from app.core.config import get_settings


@lru_cache
def _client() -> Any:
    import boto3

    settings = get_settings()
    return boto3.client("s3", region_name=settings.AWS_REGION)


def _put_object_sync(key: str, data: bytes, content_type: str) -> None:
    settings = get_settings()
    _client().put_object(Bucket=settings.S3_BUCKET, Key=key, Body=data, ContentType=content_type)


def _get_object_sync(key: str) -> bytes:
    settings = get_settings()
    response = _client().get_object(Bucket=settings.S3_BUCKET, Key=key)
    return response["Body"].read()


async def upload_bytes(key: str, data: bytes, *, content_type: str = "application/pdf") -> str:
    """Upload raw bytes to S3 under ``key``, returning the s3_key used."""
    await asyncio.to_thread(_put_object_sync, key, data, content_type)
    return key


async def download_bytes(key: str) -> bytes:
    """Download raw bytes from S3 for ``key``."""
    return await asyncio.to_thread(_get_object_sync, key)
