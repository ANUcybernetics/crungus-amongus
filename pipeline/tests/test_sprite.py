import json

import pytest
from PIL import Image

from crungus_amongus.config import Settings
from crungus_amongus.sprite import (
    CELL_PX,
    TILE_CELLS,
    TILE_COLS,
    TILE_PX,
    build_sprite,
    cell_position,
    square,
    tile_count,
    tile_name,
    tile_shape,
)


@pytest.mark.parametrize("cells", [1, 63, 64, 4095, TILE_CELLS, 4097, 20_000])
def test_every_cell_lands_on_exactly_one_tile(cells: int) -> None:
    """A synthetic corpus tiles without gaps, overlaps or overruns."""
    seen: set[tuple[int, int, int]] = set()
    shapes = [tile_shape(cells, tile) for tile in range(tile_count(cells))]
    for index in range(cells):
        tile, x, y = cell_position(index)
        assert 0 <= tile < len(shapes)
        width, height = shapes[tile]
        assert x + CELL_PX <= width and y + CELL_PX <= height
        seen.add((tile, x, y))
    assert len(seen) == cells


@pytest.mark.parametrize("cells", [1, 4097, 20_000])
def test_no_tile_exceeds_the_texture_limit(cells: int) -> None:
    for tile in range(tile_count(cells)):
        width, height = tile_shape(cells, tile)
        assert 0 < width <= TILE_PX
        assert 0 < height <= TILE_PX


def test_a_twenty_thousand_key_corpus_needs_five_tiles() -> None:
    assert tile_count(20_000) == 5
    # the last tile holds the remainder and is short, not square
    assert tile_shape(20_000, 4) == (TILE_PX, 57 * CELL_PX)  # 3616 cells over 64
    assert tile_shape(20_000, 0) == (TILE_PX, TILE_PX)


def test_cells_run_left_to_right_then_down_within_a_tile() -> None:
    assert cell_position(0) == (0, 0, 0)
    assert cell_position(1) == (0, CELL_PX, 0)
    assert cell_position(TILE_COLS) == (0, 0, CELL_PX)
    assert cell_position(TILE_CELLS) == (1, 0, 0)


def test_build_sprite_writes_tiles_and_an_index(tmp_path) -> None:
    settings = Settings(replicate_api_token="x", data_dir=tmp_path)
    for slug, count in (("owner--a", 3), ("owner--b", 2)):
        directory = settings.optimized_dir / slug / "crungus"
        directory.mkdir(parents=True)
        for i in range(count):
            Image.new("RGB", (40, 30), (i * 20, 10, 10)).save(
                directory / f"{i}.avif", format="AVIF"
            )

    out_dir = tmp_path / "atlas"
    keys = build_sprite(settings, out_dir)
    index = json.loads((out_dir / "sprite.json").read_text())

    assert index["keys"] == keys == sorted(keys)
    assert index["tiles"] == [tile_name(0)]
    assert index["cell_px"] == CELL_PX
    with Image.open(out_dir / tile_name(0)) as sheet:
        assert sheet.size == tile_shape(len(keys), 0) == (5 * CELL_PX, CELL_PX)


def test_build_sprite_clears_tiles_a_larger_corpus_left_behind(tmp_path) -> None:
    settings = Settings(replicate_api_token="x", data_dir=tmp_path)
    directory = settings.optimized_dir / "owner--a" / "crungus"
    directory.mkdir(parents=True)
    Image.new("RGB", (8, 8)).save(directory / "0.avif", format="AVIF")
    out_dir = tmp_path / "atlas"
    out_dir.mkdir()
    stale = [out_dir / "sprite.webp", out_dir / tile_name(1)]
    for path in stale:
        path.write_bytes(b"")

    build_sprite(settings, out_dir)

    assert (out_dir / tile_name(0)).exists()
    assert not any(path.exists() for path in stale)


def test_square_centre_crops_to_the_short_edge() -> None:
    cropped = square(Image.new("RGB", (100, 40)), CELL_PX)
    assert cropped.size == (CELL_PX, CELL_PX)
