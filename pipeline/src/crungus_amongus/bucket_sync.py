"""Upload the corpus and the derived renders to the public Tigris bucket.

Pattern cribbed from slop-university's ops/bucket-sync.py: boto3 against the
Tigris S3 endpoint, immutable cache-control, parallel uploads. Credentials come
from the untracked mise [env] block (CRUNGUS_S3_*), never the repo.

Two roots, and the difference between them is what may be cached forever. A
corpus key embeds the pinned model version that produced it, so its content can
never change and it ships immutable. Everything derived — the atlas sheets, the
eigencrungi, Kandinsky's filmstrips — is recomputed wholesale whenever the
corpus grows, lands back at the same key, and so must not be.
"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from .config import Settings

CACHE_CONTROL = "public, max-age=31536000, immutable"
MUTABLE_CACHE_CONTROL = "public, max-age=300"
# within the corpus tree, the atlas and eigencrungi outputs
MUTABLE_SUFFIXES = {".webp", ".json"}
CONTENT_TYPES = {
    ".avif": "image/avif",
    ".webp": "image/webp",
    ".json": "application/json",
    ".opus": "audio/ogg",
    ".m4a": "audio/mp4",
}
MAX_WORKERS = 8


@dataclass(frozen=True)
class _Upload:
    path: Path
    key: str
    cache: str


def upload_plan(settings: Settings) -> list[_Upload]:
    """Every file both roots offer, with the key and cache policy it ships under."""
    plan: list[_Upload] = []
    for root, derived in (
        (settings.optimized_dir, False),
        (settings.derived_dir, True),
    ):
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix not in CONTENT_TYPES:
                continue
            mutable = derived or path.suffix in MUTABLE_SUFFIXES
            plan.append(
                _Upload(
                    path,
                    str(path.relative_to(root)),
                    MUTABLE_CACHE_CONTROL if mutable else CACHE_CONTROL,
                )
            )
    return plan


def sync_optimized(settings: Settings, force: bool = False) -> tuple[int, int]:
    """Upload both roots to the bucket. Returns (uploaded, skipped)."""
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

    files = upload_plan(settings)
    pending = [
        item
        for item in files
        if force or existing.get(item.key) != item.path.stat().st_size
    ]
    logger.info(
        "sync: {} to upload, {} already in bucket",
        len(pending),
        len(files) - len(pending),
    )

    def upload(item: _Upload) -> None:
        s3.upload_file(
            str(item.path),
            settings.s3_bucket,
            item.key,
            ExtraArgs={
                "ContentType": CONTENT_TYPES[item.path.suffix],
                "CacheControl": item.cache,
            },
        )

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        list(pool.map(upload, pending))

    logger.info("sync: uploaded {} files to {}", len(pending), settings.s3_bucket)
    return len(pending), len(files) - len(pending)
