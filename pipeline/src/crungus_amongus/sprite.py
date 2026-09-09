"""Atlas sprite: every image as a small square cell in a tiled texture.

The atlas page draws every thumbnail on a pan/zoom canvas; loading them as
individual files would mean thousands of requests and a punishing build, so
publish composes the corpus into sprite tiles plus a JSON index (cell size,
tile geometry, key order). One sheet does not scale: at 16 000 images it would
be an 8128x8064 WebP, a quarter of a gigabyte decoded and beyond what a phone
will open. So the corpus is split across tiles of at most TILE_PX square, in
key order, and the page fetches only the tiles the viewport actually needs.

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
# a tile edge no browser struggles to decode; one 4096² tile holds 4096 cells
TILE_PX = 4096
TILE_COLS = TILE_PX // CELL_PX
TILE_CELLS = TILE_COLS * TILE_COLS
BACKGROUND = (23, 20, 15)


def square(img: Image.Image, side: int) -> Image.Image:
    """Centre-crop to a square and resize to side×side RGB."""
    img = img.convert("RGB")
    edge = min(img.size)
    left = (img.width - edge) // 2
    top = (img.height - edge) // 2
    img = img.crop((left, top, left + edge, top + edge))
    return img.resize((side, side), Image.Resampling.LANCZOS)


def tile_count(cells: int) -> int:
    return math.ceil(cells / TILE_CELLS)


def cell_position(index: int) -> tuple[int, int, int]:
    """(tile, x, y) in pixels for the index-th cell in key order."""
    tile, within = divmod(index, TILE_CELLS)
    return tile, (within % TILE_COLS) * CELL_PX, (within // TILE_COLS) * CELL_PX


def tile_shape(cells: int, tile: int) -> tuple[int, int]:
    """(width, height) in pixels of one tile of a `cells`-cell corpus.

    Only the last tile is short, and a corpus smaller than one tile row is
    narrow as well: no point encoding empty pixels.
    """
    held = min(cells - tile * TILE_CELLS, TILE_CELLS)
    return min(held, TILE_COLS) * CELL_PX, math.ceil(held / TILE_COLS) * CELL_PX


def tile_name(tile: int) -> str:
    return f"sprite-{tile:03d}.webp"


def build_sprite(settings: Settings, out_dir: Path | None = None) -> list[str]:
    """Compose data/optimized/**.avif into sprite-NNN.webp + sprite.json."""
    if out_dir is None:
        out_dir = settings.optimized_dir / "atlas"
    files = sorted(settings.optimized_dir.rglob("*.avif"))
    keys = [str(p.relative_to(settings.optimized_dir)) for p in files]
    if not keys:
        logger.warning("sprite: no optimized images")
        return []

    out_dir.mkdir(parents=True, exist_ok=True)
    tiles = tile_count(len(keys))
    for tile in range(tiles):
        sheet = Image.new("RGB", tile_shape(len(keys), tile), BACKGROUND)
        start = tile * TILE_CELLS
        for index in range(start, min(start + TILE_CELLS, len(keys))):
            _, x, y = cell_position(index)
            with Image.open(files[index]) as img:
                sheet.paste(square(img, CELL_PX), (x, y))
        sheet.save(out_dir / tile_name(tile), format="WEBP", quality=62, method=6)
        logger.info("sprite: tile {}/{} {}", tile + 1, tiles, sheet.size)

    index = {
        "cell_px": CELL_PX,
        "tile_cols": TILE_COLS,
        "tile_cells": TILE_CELLS,
        "tiles": [tile_name(tile) for tile in range(tiles)],
        "keys": keys,
    }
    (out_dir / "sprite.json").write_text(json.dumps(index) + "\n")
    _remove_stale(out_dir, tiles)
    logger.info("sprite: {} cells across {} tiles → {}", len(keys), tiles, out_dir)
    return keys


def _remove_stale(out_dir: Path, tiles: int) -> None:
    """Drop tiles a smaller corpus left behind, and the pre-tiling single sheet."""
    current = {tile_name(tile) for tile in range(tiles)}
    for path in [*out_dir.glob("sprite-*.webp"), out_dir / "sprite.webp"]:
        if path.name not in current and path.exists():
            path.unlink()
            logger.info("sprite: removed stale {}", path.name)
