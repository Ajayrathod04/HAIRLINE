"""Binary storage: local directory (default) or a PRIVATE S3 bucket. Files are only served via the API."""
from __future__ import annotations
import os
import re

_SAFE = re.compile(r"^[A-Za-z0-9_\-./]+$")


def _check(key: str) -> str:
    if not _SAFE.match(key) or ".." in key or key.startswith("/"):
        raise ValueError("bad blob key")
    return key


class LocalBlobs:
    name = "local"

    def __init__(self, root: str):
        self.root = os.path.abspath(root)
        os.makedirs(self.root, exist_ok=True)

    def put(self, key: str, data: bytes, ctype: str = "application/octet-stream") -> None:
        path = os.path.join(self.root, _check(key))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)

    def get(self, key: str):
        path = os.path.join(self.root, _check(key))
        if not os.path.isfile(path):
            return None
        with open(path, "rb") as f:
            return f.read()


class S3Blobs:
    """UNVERIFIED against a live bucket in this build."""
    name = "s3"

    def __init__(self, bucket: str, region: str):
        import boto3
        self.bucket = bucket
        self.c = boto3.client("s3", region_name=region)

    def put(self, key, data, ctype="application/octet-stream"):
        self.c.put_object(Bucket=self.bucket, Key=_check(key), Body=data, ContentType=ctype,
                          ServerSideEncryption="AES256")

    def get(self, key):
        try:
            return self.c.get_object(Bucket=self.bucket, Key=_check(key))["Body"].read()
        except self.c.exceptions.NoSuchKey:
            return None


def make_blobs(cfg):
    if cfg.blob_backend == "s3":
        return S3Blobs(cfg.s3_bucket, cfg.aws_region)
    return LocalBlobs(cfg.blob_dir)
