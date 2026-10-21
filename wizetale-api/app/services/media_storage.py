"""Private media storage adapters used by completed story assets."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.config import settings


class R2MediaStorage:
    def __init__(self, client: Any | None = None):
        self.client = client

    def _client(self):
        if self.client is None:
            required = (
                settings.R2_ENDPOINT_URL,
                settings.R2_ACCESS_KEY_ID,
                settings.R2_SECRET_ACCESS_KEY,
                settings.R2_BUCKET_NAME,
            )
            if not all(required):
                raise RuntimeError("Cloudflare R2 media storage is not configured")
            import boto3
            from botocore.config import Config

            self.client = boto3.client(
                "s3",
                endpoint_url=settings.R2_ENDPOINT_URL,
                aws_access_key_id=settings.R2_ACCESS_KEY_ID,
                aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
                region_name="auto",
                config=Config(signature_version="s3v4"),
            )
        return self.client

    def upload(self, *, object_path: str, local_path: str, content_type: str) -> str:
        path = "/".join(part for part in object_path.split("/") if part)
        with Path(local_path).open("rb") as asset:
            self._client().put_object(
                Bucket=settings.R2_BUCKET_NAME,
                Key=path,
                Body=asset,
                ContentType=content_type,
            )
        return path

    def signed_url(self, object_path: str, expires_in: int | None = None) -> str:
        ttl = expires_in or settings.MEDIA_SIGNED_URL_TTL_SECONDS
        if ttl > 86400:
            raise ValueError("Media signed URLs may not live longer than one day")
        return self._client().generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.R2_BUCKET_NAME, "Key": object_path},
            ExpiresIn=ttl,
        )

    def delete_user_assets(self, user_id: str) -> int:
        """Delete all objects beneath one user's isolated object prefix."""
        if not user_id or "/" in user_id or user_id in {".", ".."}:
            raise ValueError("Invalid user ID for media cleanup")
        prefix = f"{user_id}/"
        client = self._client()
        deleted = 0
        batch: list[dict[str, str]] = []

        def delete_batch() -> None:
            nonlocal deleted
            if not batch:
                return
            result = client.delete_objects(
                Bucket=settings.R2_BUCKET_NAME,
                Delete={"Objects": list(batch), "Quiet": True},
            )
            errors = result.get("Errors", [])
            if errors:
                raise RuntimeError("Could not delete all user media from R2")
            deleted += len(batch)
            batch.clear()

        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=settings.R2_BUCKET_NAME, Prefix=prefix):
            for item in page.get("Contents", []):
                key = item.get("Key")
                if key and key.startswith(prefix):
                    batch.append({"Key": key})
                    if len(batch) == 1000:
                        delete_batch()
        delete_batch()
        return deleted

    def delete_asset(self, object_path: str) -> None:
        if not object_path or any(part in {'', '.', '..'} for part in object_path.split('/')):
            raise ValueError('Invalid media object path')
        self._client().delete_object(Bucket=settings.R2_BUCKET_NAME, Key=object_path)

    def delete_job_assets(self, user_id: str, job_id: str) -> int:
        """Remove only one generation job's objects from its isolated prefix."""
        if not user_id or "/" in user_id or user_id in {".", ".."}:
            raise ValueError("Invalid user ID for media cleanup")
        if not job_id or "/" in job_id or job_id in {".", ".."}:
            raise ValueError("Invalid job ID for media cleanup")
        prefix = f"{user_id}/{job_id}/"
        client = self._client()
        objects = [
            {"Key": item["Key"]}
            for page in client.get_paginator("list_objects_v2").paginate(
                Bucket=settings.R2_BUCKET_NAME, Prefix=prefix
            )
            for item in page.get("Contents", [])
            if item.get("Key", "").startswith(prefix)
        ]
        deleted = 0
        for start in range(0, len(objects), 1000):
            result = client.delete_objects(
                Bucket=settings.R2_BUCKET_NAME,
                Delete={"Objects": objects[start : start + 1000], "Quiet": True},
            )
            if result.get("Errors", []):
                raise RuntimeError("Could not remove media from the cancelled generation")
            deleted += len(objects[start : start + 1000])
        return deleted


r2_media_storage = R2MediaStorage()
