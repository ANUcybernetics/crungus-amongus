import { describe, expect, it } from "vitest";

import { siteData } from "../src/lib/data";
import { generatedModels } from "../src/lib/models";
import { itemAnchor, itemNumber, itemPath } from "../src/lib/permalink";

describe("item permalinks", () => {
  it("point at the item's model page, numbered from 1", () => {
    expect(itemPath("sdxl--sdxl/crungus/6.avif")).toBe("/model/sdxl--sdxl/#crungus-7");
    expect(itemPath("riffusion--riffusion/a-crungus/0.opus")).toBe(
      "/model/riffusion--riffusion/#a-crungus-1",
    );
    expect(itemNumber("sdxl--sdxl/crungus/6.avif")).toBe(7);
  });

  it("give every item in the archive a distinct anchor on its model page", () => {
    for (const model of generatedModels(siteData)) {
      const keys = model.prompts.flatMap((p) => [
        ...p.images.map((i) => i.key),
        ...p.clips.map((c) => c.opus),
      ]);
      const anchors = new Set(keys.map(itemAnchor));
      expect(anchors.size).toBe(keys.length);
      for (const key of keys) expect(itemPath(key)).toContain(`/model/${model.slug}/#`);
    }
  });

  it("refuse a key that isn't an item's", () => {
    expect(() => itemAnchor("meshes.json")).toThrow();
  });
});
