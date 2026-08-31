"""Originals → AVIF via Pillow resize + avifenc (settings cribbed from
slop-university's ops/encode-images.py)."""

import subprocess
import tempfile
from pathlib import Path

from loguru import logger
from PIL import Image

from .config import Settings

MAX_DIM = 1536
AVIFENC_ARGS = [
    "-j",
    "4",
    "-s",
    "6",
    "--min",
    "0",
    "--max",
    "63",
    "-a",
    "end-usage=q",
    "-a",
    "cq-level=28",
]


def optimize_all(settings: Settings, force: bool = False) -> tuple[int, int]:
    """Encode every original to data/optimized/<same-relative-path>.avif.

    Returns (encoded, skipped). Incremental: an up-to-date output is skipped.
    """
    encoded = skipped = 0
    originals = sorted(p for p in settings.originals_dir.rglob("*") if p.is_file())
    for source in originals:
        relative = source.relative_to(settings.originals_dir)
        dest = settings.optimized_dir / relative.with_suffix(".avif")
        if (
            not force
            and dest.exists()
            and dest.stat().st_mtime >= source.stat().st_mtime
        ):
            skipped += 1
            continue
        encode_avif(source, dest)
        encoded += 1
    logger.info("optimize: {} encoded, {} up to date", encoded, skipped)
    return encoded, skipped


def encode_avif(source: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        image = image.convert("RGB")
        if max(image.size) > MAX_DIM:
            image.thumbnail((MAX_DIM, MAX_DIM), Image.Resampling.LANCZOS)
        with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
            image.save(tmp.name, format="PNG")
            subprocess.run(
                ["avifenc", *AVIFENC_ARGS, tmp.name, str(dest)],
                check=True,
                capture_output=True,
            )
