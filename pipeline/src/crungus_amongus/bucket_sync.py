"""Upload the optimized AVIF tree to the public Tigris bucket.

Pattern cribbed from slop-university's ops/bucket-sync.py: boto3 against the
Tigris S3 endpoint, immutable cache-control (safe: keys embed the pinned model
version's content — regenerated content lands at new paths), parallel uploads.
Credentials come from the untracked mise [env] block (CRUNGUS_S3_*), never the
repo.
"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from loguru import logger

from .config import Settings

CACHE_CONTROL = "public, max-age=31536000, immutable"
# the sprite index/sheet change per corpus regeneration, so they get a short
# cache instead of immutable
MUTABLE_CACHE_CONTROL = "public, max-age=300"
MUTABLE_SUFFIXES = {".webp", ".json"}
CONTENT_TYPES = {
    ".avif": "image/avif",
    ".webp": "image/webp",
    ".json": "application/json",
}
MAX_WORKERS = 8


def sync_optimized(settings: Settings, force: bool = False) -> tuple[int, int]:
    """Upload data/optimized/** to the bucket. Returns (uploaded, skipped)."""
    import boto3

    if not (settings.s3_access_key_id and settings.s3_secret_access_key):
        raise RuntimeError(
            "CRUNGUS_S3_ACCESS_KEY_ID / CRUNGUS_S3_SECRET_ACCESS_KEY not set "
            "(add them to the [env] block of ~/.config/mise/config.local.toml)"
        )

    s3 = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        region_name="auto",
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=settings.s3_secret_access_key,
    )

    # the atlas page fetch()es the sprite cross-origin, which needs CORS;
    # public GET/HEAD from anywhere is exactly what a public bucket means
    s3.put_bucket_cors(
        Bucket=settings.s3_bucket,
        CORSConfiguration={
            "CORSRules": [
                {
                    "AllowedMethods": ["GET", "HEAD"],
                    "AllowedOrigins": ["*"],
                    "AllowedHeaders": ["*"],
                    "MaxAgeSeconds": 86400,
                }
            ]
        },
    )

    existing: dict[str, int] = {}
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=settings.s3_bucket):
        for obj in page.get("Contents", []):
            existing[obj["Key"]] = obj["Size"]

    files = sorted(
        p
        for p in settings.optimized_dir.rglob("*")
        if p.is_file() and p.suffix in CONTENT_TYPES
    )
    pending: list[tuple[Path, str]] = []
    for path in files:
        key = str(path.relative_to(settings.optimized_dir))
        if force or existing.get(key) != path.stat().st_size:
            pending.append((path, key))
    logger.info(
        "sync: {} to upload, {} already in bucket",
        len(pending),
        len(files) - len(pending),
    )

    def upload(item: tuple[Path, str]) -> None:
        path, key = item
        cache = (
            MUTABLE_CACHE_CONTROL if path.suffix in MUTABLE_SUFFIXES else CACHE_CONTROL
        )
        s3.upload_file(
            str(path),
            settings.s3_bucket,
            key,
            ExtraArgs={
                "ContentType": CONTENT_TYPES[path.suffix],
                "CacheControl": cache,
            },
        )

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        list(pool.map(upload, pending))

    logger.info("sync: uploaded {} files to {}", len(pending), settings.s3_bucket)
    return len(pending), len(files) - len(pending)
