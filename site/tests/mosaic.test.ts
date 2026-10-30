import { describe, expect, it } from "vitest";

import { siteData } from "../src/lib/data";
import { generatedModels, imageCount } from "../src/lib/models";
import {
  blockCells,
  mosaicData,
  openBlock,
  relatives,
  ringCells,
  shuffleBag,
  tilesFor,
} from "../src/lib/mosaic";

const data = mosaicData(siteData, ({ key }) => ({
  srcset: `/thumb/${key} 240w`,
  full: `/full/${key}`,
  page: `/page/${key}`,
}));

describe("mosaic tiles", () => {
  it("offers every image in the archive, labelled with its model and prompt", () => {
    const models = generatedModels(siteData, "image");
    const tiles = tilesFor(data);
    expect(tiles.length).toBe(models.reduce((n, m) => n + imageCount(m), 0));
    for (const tile of tiles) {
      expect(tile.srcset.startsWith(`/thumb/${tile.model.slug}/`)).toBe(true);
      expect(tile.full.startsWith(`/full/${tile.model.slug}/`)).toBe(true);
      expect(tile.prompt).not.toBe("");
    }
  });

  it("narrows to one model, and falls back to all for an unknown one", () => {
    const model = data.models[0]!;
    const tiles = tilesFor(data, model.slug);
    expect(tiles.length).toBeGreaterThan(0);
    expect(tiles.every((t) => t.model === model)).toBe(true);
    expect(tilesFor(data, "no-such-model")).toEqual(tilesFor(data));
  });
});

describe("opening a tile", () => {
  it("offers the other images from the tile's model and prompt", () => {
    const tile = tilesFor(data)[0]!;
    const kin = relatives(tile);
    const prompt = tile.model.prompts.find((p) => p.prompt === tile.prompt)!;
    expect(kin.length).toBe(prompt.images.length - 1);
    expect(kin.every((t) => t.model === tile.model && t.prompt === tile.prompt)).toBe(true);
    expect(kin.some((t) => t.page === tile.page)).toBe(false);
  });

  it("centres the block on the tapped cell, kept inside the grid", () => {
    // 16 × 9: cell 20 is column 4, row 1
    expect(openBlock(20, 16, 9, 3)).toEqual({ col: 3, row: 0, span: 3 });
    expect(openBlock(0, 16, 9, 3)).toEqual({ col: 0, row: 0, span: 3 });
    expect(openBlock(143, 16, 9, 3)).toEqual({ col: 13, row: 6, span: 3 });
    // a phone's 2 × 4 wall can only open two cells a side
    expect(openBlock(7, 2, 4, 3)).toEqual({ col: 0, row: 2, span: 2 });
  });

  it("lists the block's cells and the ring around it, nearest the tap first", () => {
    const block = openBlock(0, 16, 9, 3);
    expect(blockCells(block, 16)).toEqual([0, 1, 2, 16, 17, 18, 32, 33, 34]);
    const ring = ringCells(block, 1, 0, 16, 9);
    // clipped at the grid's edges, so only the right and bottom sides remain
    expect(ring.toSorted((a, b) => a - b)).toEqual([3, 19, 35, 48, 49, 50, 51]);
    expect(ring[0]).toBe(3);
    expect(ring.at(-1)).toBe(51);
  });
});

describe("shuffle bag", () => {
  it("draws every item once before any repeats", () => {
    const items = [1, 2, 3, 4, 5];
    const draw = shuffleBag(items);
    for (let round = 0; round < 3; round++) {
      const drawn = items.map(() => draw());
      expect(drawn.toSorted()).toEqual(items);
    }
  });
});
