import { describe, expect, it } from "vitest";

import { cellFinder, tileNames, type SpriteIndex } from "../src/lib/sprite";

const CELL = 64;
const TILE_COLS = 64;
const TILE_CELLS = TILE_COLS * TILE_COLS;

function index(count: number, overrides: Partial<SpriteIndex> = {}): SpriteIndex {
  return {
    cell_px: CELL,
    tile_cols: TILE_COLS,
    tile_cells: TILE_CELLS,
    tiles: Array.from(
      { length: Math.ceil(count / TILE_CELLS) },
      (_, i) => `sprite-${String(i).padStart(3, "0")}.webp`,
    ),
    keys: Array.from({ length: count }, (_, i) => `m/p/${i}.avif`),
    ...overrides,
  };
}

describe("sprite tiles", () => {
  it("runs cells left to right then down, then on to the next tile", () => {
    const find = cellFinder(index(TILE_CELLS + 1));
    expect(find("m/p/0.avif")).toEqual({ tile: 0, x: 0, y: 0 });
    expect(find("m/p/1.avif")).toEqual({ tile: 0, x: CELL, y: 0 });
    expect(find(`m/p/${TILE_COLS}.avif`)).toEqual({ tile: 0, x: 0, y: CELL });
    expect(find(`m/p/${TILE_CELLS}.avif`)).toEqual({ tile: 1, x: 0, y: 0 });
  });

  it("gives a twenty-thousand-key corpus one place per key across five tiles", () => {
    const spriteIndex = index(20_000);
    const find = cellFinder(spriteIndex);
    expect(tileNames(spriteIndex)).toHaveLength(5);
    const seen = new Set<string>();
    for (const key of spriteIndex.keys) {
      const cell = find(key)!;
      expect(cell.tile).toBeLessThan(5);
      expect(cell.x).toBeLessThan(4096);
      expect(cell.y).toBeLessThan(4096);
      seen.add(`${cell.tile}:${cell.x}:${cell.y}`);
    }
    expect(seen.size).toBe(20_000);
  });

  it("has nothing for a key that is not in the corpus", () => {
    expect(cellFinder(index(4))("nobody/p/0.avif")).toBeUndefined();
  });

  it("reads the pre-tiling layout as one unbounded sheet", () => {
    const older: SpriteIndex = {
      cell_px: CELL,
      cols: 40,
      keys: Array.from({ length: 5000 }, (_, i) => `m/p/${i}.avif`),
    };
    expect(tileNames(older)).toEqual(["sprite.webp"]);
    const find = cellFinder(older);
    expect(find("m/p/41.avif")).toEqual({ tile: 0, x: CELL, y: CELL });
    // past where a tile would have ended, still on the one sheet
    expect(find("m/p/4999.avif")).toEqual({ tile: 0, x: 39 * CELL, y: 124 * CELL });
  });
});
