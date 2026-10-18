import { describe, expect, it } from "vitest";

import { siteData } from "../src/lib/data";
import { generatedModels, imageCount } from "../src/lib/models";
import { mosaicData, shuffleBag, tilesFor } from "../src/lib/mosaic";

const data = mosaicData(siteData, (key) => ({
  srcset: `/thumb/${key} 240w`,
  full: `/full/${key}`,
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

  it("leaves out images that are not synced, and models left with none", () => {
    const first = data.models[0]!.slug;
    const partial = mosaicData(siteData, (key) =>
      key.startsWith(`${first}/`) ? null : { srcset: key, full: key },
    );
    expect(partial.models.map((m) => m.slug)).toEqual(data.models.slice(1).map((m) => m.slug));
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
