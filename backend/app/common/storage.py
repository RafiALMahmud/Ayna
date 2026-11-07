import hashlib
import hmac
import time
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Protocol

import boto3
from botocore.config import Config

from app.common.config import get_settings


class Storage(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> None: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...
    def ready(self) -> None: ...


class LocalStorage:
    def __init__(self, root: str):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root) or ".." in PurePosixPath(key).parts:
            raise ValueError("Invalid storage key")
        return path

    def put(self, key: str, data: bytes, content_type: str) -> None:
        target = self.path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def get(self, key: str) -> bytes:
        return self.path(key).read_bytes()

    def delete(self, key: str) -> None:
        self.path(key).unlink(missing_ok=True)

    def ready(self) -> None:
        if not self.root.is_dir():
            raise OSError("Storage unavailable")


class S3Storage:
    def __init__(self):
        settings = get_settings()
        self.bucket = settings.s3_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)

    def get(self, key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def ready(self) -> None:
        self.client.head_bucket(Bucket=self.bucket)


@lru_cache
def get_storage() -> Storage:
    settings = get_settings()
    return (
        S3Storage()
        if settings.storage_backend == "s3"
        else LocalStorage(settings.local_storage_path)
    )


def asset_url(kind: str, asset_id: str, owner: str) -> str:
    settings = get_settings()
    expires = int(time.time()) + settings.asset_ttl_seconds
    payload = f"{kind}:{asset_id}:{owner}:{expires}"
    signature = hmac.new(settings.asset_signing_key.encode(), payload.encode(), hashlib.sha256)
    return (
        f"/api/v1/assets/{kind}/{asset_id}?owner={owner}"
        f"&expires={expires}&sig={signature.hexdigest()}"
    )


def verify_asset(kind: str, asset_id: str, owner: str, expires: int, sig: str) -> bool:
    payload = f"{kind}:{asset_id}:{owner}:{expires}"
    expected = hmac.new(
        get_settings().asset_signing_key.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()
    return expires >= int(time.time()) and hmac.compare_digest(expected, sig)
