import { describe, expect, it } from "vitest";

import { siteData } from "../src/lib/data";
import {
  byCrungusness,
  byTimeline,
  coverImage,
  crungusness,
  failedModels,
  generatedModels,
  imageCount,
} from "../src/lib/models";
import type { ModelEntry } from "../src/lib/schema";

describe("dataset integrity", () => {
  it("parses the contract (data.ts throws otherwise)", () => {
    expect(siteData.models.length).toBeGreaterThan(0);
  });

  it("every image key is a well-formed relative avif path", () => {
    for (const model of siteData.models) {
      for (const prompt of model.prompts) {
        for (const image of prompt.images) {
          expect(image.key).toMatch(/^[a-z0-9-]+\/[a-z0-9-]+\/\d\.avif$/);
          expect(image.key.startsWith(model.slug)).toBe(true);
        }
      }
    }
  });

  it("slugs are unique", () => {
    const slugs = siteData.models.map((m) => m.slug);
    expect(new Set(slugs).size).toBe(slugs.length);
  });
});

function fakeModel(overrides: Partial<ModelEntry>): ModelEntry {
  return {
    slug: "test--model",
    owner: "test",
    name: "model",
    version_id: "v1",
    description: null,
    source: "collection",
    is_official: false,
    release_date: "2023-01-01",
    replicate_url: "https://replicate.com/test/model",
    status: "ok",
    notes: null,
    prompts: [
      {
        prompt: "crungus",
        prompt_slug: "crungus",
        consistency: 0.8,
        images: [{ key: "test--model/crungus/0.avif", atlas: [0.1, 0.2], typicality: 0.7 }],
      },
      {
        prompt: "a picture of a crungus",
        prompt_slug: "a-picture-of-a-crungus",
        consistency: 0.5,
        images: [],
      },
    ],
    ...overrides,
  };
}

describe("helpers", () => {
  it("crungusness is the max consistency across prompts", () => {
    expect(crungusness(fakeModel({}))).toBe(0.8);
  });

  it("coverImage prefers the bare-word prompt", () => {
    expect(coverImage(fakeModel({}))).toBe("test--model/crungus/0.avif");
  });

  it("generated/failed partition is by image count and pending is excluded", () => {
    const generated = fakeModel({});
    const failed = fakeModel({ slug: "b", status: "failed", prompts: [] });
    const pending = fakeModel({ slug: "c", status: "pending", prompts: [] });
    const data = { ...siteData, models: [generated, failed, pending] };
    expect(generatedModels(data).map((m) => m.slug)).toEqual(["test--model"]);
    expect(failedModels(data).map((m) => m.slug)).toEqual(["b"]);
    expect(imageCount(generated)).toBe(1);
  });

  it("byTimeline sorts by date with undated last, byCrungusness descends", () => {
    const a = fakeModel({ slug: "a", release_date: "2024-01-01" });
    const b = fakeModel({ slug: "b", release_date: "2022-01-01" });
    const c = fakeModel({ slug: "c", release_date: null, prompts: [] });
    expect(byTimeline([a, c, b]).map((m) => m.slug)).toEqual(["b", "a", "c"]);
    expect(byCrungusness([c, a]).map((m) => m.slug)).toEqual(["a", "c"]);
  });
});
