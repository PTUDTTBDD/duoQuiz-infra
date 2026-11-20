"""Boto3 client wrapper for MinIO / S3-compatible object storage."""

from __future__ import annotations

from pathlib import Path

import boto3
from botocore.client import Config


class S3StorageClient:
    def __init__(self, endpoint_url: str, bucket: str, access_key: str, secret_key: str) -> None:
        self.bucket = bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",
        )

    def download_file(self, key: str, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        self.client.download_file(self.bucket, key, str(destination))

    def upload_file(self, source: Path, key: str, content_type: str) -> None:
        self.client.upload_file(
            str(source),
            self.bucket,
            key,
            ExtraArgs={"ContentType": content_type},
        )

