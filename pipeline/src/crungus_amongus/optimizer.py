"""Originals → web formats.

Images: Pillow resize + avifenc (settings cribbed from slop-university's
ops/encode-images.py). Audio: ffmpeg to Opus (the modern, efficient choice)
plus an AAC fallback, because Safari on macOS only plays Opus inside a CAF
container; the site picks whichever the browser can play. Both audio encodes
apply EBU R128 loudness normalisation so the radio doesn't lurch between
models mastered at wildly different levels.
"""

import subprocess
import tempfile
from pathlib import Path

from loguru import logger
from PIL import Image, UnidentifiedImageError

from .config import Settings
from .output_normalizer import AUDIO_EXTENSIONS

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
    encoded = skipped = failed = 0
    originals = sorted(p for p in settings.originals_dir.rglob("*") if p.is_file())
    for source in originals:
        relative = source.relative_to(settings.originals_dir)
        is_audio = source.suffix.lower() in AUDIO_EXTENSIONS
        suffixes = list(AUDIO_ENCODES) if is_audio else [".avif"]
        for suffix in suffixes:
            dest = settings.optimized_dir / relative.with_suffix(suffix)
            if (
                not force
                and dest.exists()
                and dest.stat().st_mtime >= source.stat().st_mtime
            ):
                skipped += 1
                continue
            try:
                if is_audio:
                    encode_audio(source, dest)
                else:
                    encode_avif(source, dest)
                encoded += 1
            except (
                UnidentifiedImageError,
                OSError,
                subprocess.CalledProcessError,
            ) as exc:
                failed += 1
                logger.warning("optimize: skipping {}: {}", dest.name, exc)
    logger.info(
        "optimize: {} encoded, {} up to date, {} unreadable", encoded, skipped, failed
    )
    return encoded, skipped, failed


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
