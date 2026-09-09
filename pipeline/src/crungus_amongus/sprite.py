"""Atlas sprite sheet: every image as a small square cell in one texture.

The atlas page draws ~1800 thumbnails on a pan/zoom canvas; loading them as
individual files would mean ~1800 requests and a punishing build, so publish
composes one WebP sprite plus a JSON index (cell size, columns, key order).
Written into the optimized tree so sync uploads it to the bucket alongside the
images — the atlas page fetches it from there, keeping the blob out of git.
"""

import json
import math
from pathlib import Path

from loguru import logger
from PIL import Image

from .config import Settings

CELL_PX = 64


def square(img: Image.Image, side: int) -> Image.Image:
    """Centre-crop to a square and resize to side×side RGB."""
    img = img.convert("RGB")
    edge = min(img.size)
    left = (img.width - edge) // 2
    top = (img.height - edge) // 2
    img = img.crop((left, top, left + edge, top + edge))
    return img.resize((side, side), Image.Resampling.LANCZOS)


def build_sprite(settings: Settings, out_dir: Path | None = None) -> list[str]:
    """Compose data/optimized/**.avif into sprite.webp + sprite.json."""
    if out_dir is None:
        out_dir = settings.optimized_dir / "atlas"
    files = sorted(settings.optimized_dir.rglob("*.avif"))
    keys = [str(p.relative_to(settings.optimized_dir)) for p in files]
    if not keys:
        logger.warning("sprite: no optimized images")
        return []

    cols = math.ceil(math.sqrt(len(keys)))
    rows = math.ceil(len(keys) / cols)
    sheet = Image.new("RGB", (cols * CELL_PX, rows * CELL_PX), (23, 20, 15))
    for i, path in enumerate(files):
        with Image.open(path) as img:
            sheet.paste(
                square(img, CELL_PX), ((i % cols) * CELL_PX, (i // cols) * CELL_PX)
            )

    out_dir.mkdir(parents=True, exist_ok=True)
    sheet.save(out_dir / "sprite.webp", format="WEBP", quality=62, method=6)
    index = {"cell_px": CELL_PX, "cols": cols, "keys": keys}
    (out_dir / "sprite.json").write_text(json.dumps(index) + "\n")
    logger.info(
        "sprite: {} cells ({}x{}) → {}", len(keys), cols, rows, out_dir / "sprite.webp"
    )
    return keys
