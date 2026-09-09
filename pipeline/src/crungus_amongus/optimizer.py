"""Originals → web formats.

Images: Pillow resize + avifenc (settings cribbed from slop-university's
ops/encode-images.py). Audio: ffmpeg to Opus (the modern, efficient choice)
plus an AAC fallback, because Safari on macOS only plays Opus inside a CAF
container; the site picks whichever the browser can play. Both audio encodes
apply EBU R128 loudness normalisation so the radio doesn't lurch between
models mastered at wildly different levels.
"""

import os
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from loguru import logger
from PIL import Image, UnidentifiedImageError

from .config import Settings
from .output_normalizer import AUDIO_EXTENSIONS

MAX_DIM = 1536
# Encoding is one avifenc/ffmpeg process per file, so it parallelises cleanly:
# the threads spend their lives in subprocess.run with the GIL released. Each
# avifenc gets AVIF_THREADS of its own, so the two multiply — keep the product
# near the core count rather than oversubscribing.
AVIF_THREADS = 4
MAX_WORKERS = max(1, (os.cpu_count() or 8) // AVIF_THREADS)
AVIFENC_ARGS = [
    "-j",
    str(AVIF_THREADS),
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
LOUDNORM = "loudnorm=I=-16:TP=-1.5:LRA=11"
# loudnorm resamples internally (to 192 kHz), so pin the output rate
SAMPLE_RATE = "48000"
AUDIO_ENCODES: dict[str, list[str]] = {
    ".opus": ["-c:a", "libopus", "-b:a", "64k", "-vbr", "on"],
    ".m4a": ["-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart"],
}


def optimize_all(settings: Settings, force: bool = False) -> tuple[int, int, int]:
    """Encode every original under data/optimized/ at the same relative path.

    Returns (encoded, skipped, failed), counting output files. Incremental: an
    up-to-date output is skipped. A single unreadable file is logged and
    skipped, never fatal — publish only advertises outputs that exist
    post-optimisation.
    """
    pending: list[_Encode] = []
    skipped = 0
    originals = sorted(p for p in settings.originals_dir.rglob("*") if p.is_file())
    for source in originals:
        relative = source.relative_to(settings.originals_dir)
        is_audio = source.suffix.lower() in AUDIO_EXTENSIONS
        for suffix in list(AUDIO_ENCODES) if is_audio else [".avif"]:
            dest = settings.optimized_dir / relative.with_suffix(suffix)
            if (
                not force
                and dest.exists()
                and dest.stat().st_mtime >= source.stat().st_mtime
            ):
                skipped += 1
                continue
            pending.append(_Encode(source, dest, is_audio))

    logger.info(
        "optimize: {} to encode, {} up to date ({} workers)",
        len(pending),
        skipped,
        MAX_WORKERS,
    )
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        results = list(pool.map(_encode_one, pending))
    encoded = sum(results)
    failed = len(results) - encoded
    logger.info(
        "optimize: {} encoded, {} up to date, {} unreadable", encoded, skipped, failed
    )
    return encoded, skipped, failed


@dataclass(frozen=True)
class _Encode:
    source: Path
    dest: Path
    is_audio: bool


def _encode_one(job: _Encode) -> bool:
    """One file, never fatal: publish only advertises outputs that exist."""
    try:
        if job.is_audio:
            encode_audio(job.source, job.dest)
        else:
            encode_avif(job.source, job.dest)
    except (UnidentifiedImageError, OSError, subprocess.CalledProcessError) as exc:
        logger.warning("optimize: skipping {}: {}", job.dest.name, exc)
        return False
    return True


def encode_avif(source: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmpdir:
        raster = source
        if _is_svg(source):
            # a couple of models return actual SVG; rasterise it first
            raster = Path(tmpdir) / "raster.png"
            subprocess.run(
                [
                    "convert",
                    "-density",
                    "150",
                    "-background",
                    "#17140f",
                    str(source),
                    str(raster),
                ],
                check=True,
                capture_output=True,
            )
        with Image.open(raster) as image:
            image = image.convert("RGB")
            if max(image.size) > MAX_DIM:
                image.thumbnail((MAX_DIM, MAX_DIM), Image.Resampling.LANCZOS)
            tmp_png = Path(tmpdir) / "encoded.png"
            image.save(tmp_png, format="PNG")
            subprocess.run(
                ["avifenc", *AVIFENC_ARGS, str(tmp_png), str(dest)],
                check=True,
                capture_output=True,
            )


def encode_audio(source: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(source),
            "-vn",
            "-af",
            LOUDNORM,
            "-ar",
            SAMPLE_RATE,
            *AUDIO_ENCODES[dest.suffix],
            str(dest),
        ],
        check=True,
        capture_output=True,
    )


def _is_svg(path: Path) -> bool:
    head = path.open("rb").read(512).lstrip()
    return head.startswith(b"<svg") or (head.startswith(b"<?xml") and b"<svg" in head)
