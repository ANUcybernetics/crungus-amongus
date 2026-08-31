"""Atlas sprite sheet: every image as a small square cell in one texture.

The atlas page draws ~1800 thumbnails on a pan/zoom canvas; loading them as
individual files would mean ~1800 requests and a punishing build, so publish
composes one WebP sprite plus a JSON index (cell size, columns, key order).
"""

import json
import math
from pathlib import Path

from loguru import logger
from PIL import Image

from .config import REPO_ROOT, Settings

CELL_PX = 64
SPRITE_DIR = REPO_ROOT / "site" / "public" / "atlas"


def build_sprite(settings: Settings, out_dir: Path = SPRITE_DIR) -> list[str]:
    """Compose data/optimized/**.avif into sprite.webp + sprite.json."""
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
            img = img.convert("RGB")
            # centre-crop to square, then downscale to the cell
            side = min(img.size)
            left = (img.width - side) // 2
            top = (img.height - side) // 2
            img = img.crop((left, top, left + side, top + side))
            img = img.resize((CELL_PX, CELL_PX), Image.Resampling.LANCZOS)
            sheet.paste(img, ((i % cols) * CELL_PX, (i // cols) * CELL_PX))

    out_dir.mkdir(parents=True, exist_ok=True)
    sheet.save(out_dir / "sprite.webp", format="WEBP", quality=62, method=6)
    index = {"cell_px": CELL_PX, "cols": cols, "keys": keys}
    (out_dir / "sprite.json").write_text(json.dumps(index) + "\n")
    logger.info(
        "sprite: {} cells ({}x{}) → {}", len(keys), cols, rows, out_dir / "sprite.webp"
    )
    return keys
