import { describe, expect, it } from "vitest";

import { apiBase, audioIndex, imagesIndex, modelDetail, modelsIndex } from "../src/lib/api";
import { siteData } from "../src/lib/data";
import { clipCount, generatedModels, imageCount } from "../src/lib/models";

const base = apiBase(siteData, new URL("https://example.test"), "/");

describe("JSON API", () => {
  it("lists every image and clip in the archive with absolute bucket URLs", () => {
    const models = generatedModels(siteData);
    const { images, count } = imagesIndex(siteData, base);
    const { clips } = audioIndex(siteData, base);
    expect(count).toBe(models.reduce((n, m) => n + imageCount(m), 0));
    expect(clips.length).toBe(models.reduce((n, m) => n + clipCount(m), 0));
    for (const image of images) {
      expect(image.url.startsWith(`${siteData.image_base_url}/${image.model}/`)).toBe(true);
    }
    for (const clip of clips) {
      expect(clip.opus.startsWith(`${siteData.image_base_url}/${clip.model}/`)).toBe(true);
    }
  });

  it("the per-model files partition the full lists", () => {
    const details = generatedModels(siteData).map((m) => modelDetail(siteData, m, base));
    expect(details.flatMap((d) => d.images)).toEqual(imagesIndex(siteData, base).images);
    expect(details.flatMap((d) => d.clips)).toEqual(audioIndex(siteData, base).clips);
  });

  it("the index counts each model's outputs and links to its page and items", () => {
    const { models } = modelsIndex(siteData, base);
    expect(models.map((m) => m.slug)).toEqual(generatedModels(siteData).map((m) => m.slug));
    for (const model of models) {
      expect(model.images + model.clips).toBeGreaterThan(0);
      expect(model.page).toBe(`https://example.test/model/${model.slug}/`);
      expect(model.items).toBe(`https://example.test/api/models/${model.slug}.json`);
    }
  });

  it("builds links under a subpath deploy", () => {
    const sub = apiBase(siteData, new URL("https://example.test"), "/crungus");
    expect(modelsIndex(siteData, sub).models[0]!.items).toContain(
      "https://example.test/crungus/api/models/",
    );
  });
});
