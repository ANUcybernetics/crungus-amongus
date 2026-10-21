import { describe, expect, it } from "vitest";

import {
  apiBase,
  audioIndex,
  imagesIndex,
  meshesIndex,
  modelDetail,
  modelsIndex,
  videosIndex,
} from "../src/lib/api";
import { siteData } from "../src/lib/data";
import { clipCount, generatedModels, imageCount, videoCount } from "../src/lib/models";
import type { SiteData } from "../src/lib/schema";

const base = apiBase(siteData, new URL("https://example.test"), "/");

describe("JSON API", () => {
  it("lists every image and clip in the archive with absolute bucket URLs", () => {
    const models = generatedModels(siteData);
    const { images, count } = imagesIndex(siteData, base);
    const { clips } = audioIndex(siteData, base);
    const { videos } = videosIndex(siteData, base);
    expect(count).toBe(models.reduce((n, m) => n + imageCount(m), 0));
    expect(clips.length).toBe(models.reduce((n, m) => n + clipCount(m), 0));
    expect(videos.length).toBe(models.reduce((n, m) => n + videoCount(m), 0));
    for (const image of images) {
      expect(image.url.startsWith(`${siteData.image_base_url}/${image.model}/`)).toBe(true);
    }
    for (const clip of clips) {
      expect(clip.opus.startsWith(`${siteData.image_base_url}/${clip.model}/`)).toBe(true);
    }
    for (const video of videos) {
      for (const url of [video.av1, video.mp4, video.poster]) {
        expect(url.startsWith(`${siteData.image_base_url}/${video.model}/`)).toBe(true);
      }
    }
    for (const item of [...images, ...clips, ...videos]) {
      expect(item.page).toMatch(
        new RegExp(`^https://example\\.test/model/${item.model}/#.+-\\d+$`),
      );
    }
  });

  it("the per-model files partition the full lists", () => {
    const details = generatedModels(siteData).map((m) => modelDetail(siteData, m, base));
    expect(details.flatMap((d) => d.images)).toEqual(imagesIndex(siteData, base).images);
    expect(details.flatMap((d) => d.clips)).toEqual(audioIndex(siteData, base).clips);
    expect(details.flatMap((d) => d.videos)).toEqual(videosIndex(siteData, base).videos);
  });

  it("the index counts each model's outputs and links to its page and items", () => {
    const { models } = modelsIndex(siteData, base);
    expect(models.map((m) => m.slug)).toEqual(generatedModels(siteData).map((m) => m.slug));
    for (const model of models) {
      expect(model.images + model.clips + model.videos).toBeGreaterThan(0);
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

describe("meshes in the JSON API", () => {
  // exactly one meshed image, whatever the archive currently holds
  const meshed: SiteData = structuredClone(siteData);
  for (const m of meshed.models) for (const p of m.prompts) for (const i of p.images) delete i.mesh;
  const model = generatedModels(meshed, "image")[0]!;
  const image = model.prompts.find((p) => p.images.length > 0)!.images[0]!;
  const mesh = `meshes/${image.key.slice(0, -".avif".length)}/task-1-e1.glb`;
  image.mesh = mesh;

  it("lists each mesh with its source image", () => {
    const { meshes, count } = meshesIndex(meshed, base);
    expect(count).toBe(1);
    expect(meshes[0]).toMatchObject({
      url: `${meshed.image_base_url}/${mesh}`,
      image: `${meshed.image_base_url}/${image.key}`,
      // the image's own permalink, whose lightbox shows the mesh
      page: imagesIndex(meshed, base).images.find((i) => "mesh" in i)!.page,
      model: model.slug,
    });
  });

  it("links the mesh from its image entry, and only there", () => {
    const images = imagesIndex(meshed, base).images.filter((i) => "mesh" in i);
    expect(images).toEqual([
      expect.objectContaining({
        url: `${meshed.image_base_url}/${image.key}`,
        mesh: `${meshed.image_base_url}/${mesh}`,
      }),
    ]);
  });
});
