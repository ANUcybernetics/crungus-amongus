// Shapes of the static JSON API under /api/. Unlike models.json (the internal
// contract, keyed relative to the bucket) these are for outside consumers, so
// every URL is absolute and each item carries its model and prompt.
import { clipCount, generatedModels, imageCount } from "./models";
import type { ModelEntry, SiteData } from "./schema";

export interface ApiImage {
  url: string;
  model: string;
  prompt: string;
}

export interface ApiClip {
  opus: string;
  m4a: string;
  model: string;
  prompt: string;
}

/** Where the site and its bucket live, so the builders stay pure. */
export interface ApiBase {
  site: URL; // deployed site root, including any base path
  media: string; // bucket root, no trailing slash
}

export function apiBase(data: SiteData, site: URL | undefined, basePath: string): ApiBase {
  if (!site) throw new Error("the JSON API needs `site` set in astro.config");
  return {
    site: new URL(basePath.endsWith("/") ? basePath : `${basePath}/`, site),
    media: data.image_base_url,
  };
}

export function modelImages(model: ModelEntry, base: ApiBase): ApiImage[] {
  return model.prompts.flatMap((p) =>
    p.images.map((i) => ({ url: `${base.media}/${i.key}`, model: model.slug, prompt: p.prompt })),
  );
}

export function modelClips(model: ModelEntry, base: ApiBase): ApiClip[] {
  return model.prompts.flatMap((p) =>
    p.clips.map((c) => ({
      opus: `${base.media}/${c.opus}`,
      m4a: `${base.media}/${c.m4a}`,
      model: model.slug,
      prompt: p.prompt,
    })),
  );
}

export function modelSummary(model: ModelEntry, base: ApiBase) {
  return {
    slug: model.slug,
    owner: model.owner,
    name: model.name,
    modality: model.modality,
    release_date: model.release_date,
    description: model.description,
    replicate_url: model.replicate_url,
    images: imageCount(model),
    clips: clipCount(model),
    page: new URL(`model/${model.slug}/`, base.site).href,
    items: new URL(`api/models/${model.slug}.json`, base.site).href,
  };
}

/** /api/models.json: every model with at least one output, without the outputs. */
export function modelsIndex(data: SiteData, base: ApiBase) {
  const models = generatedModels(data).map((m) => modelSummary(m, base));
  return { generated_at: data.generated_at, count: models.length, models };
}

/** /api/models/<slug>.json: one model and everything it produced. */
export function modelDetail(data: SiteData, model: ModelEntry, base: ApiBase) {
  return {
    generated_at: data.generated_at,
    ...modelSummary(model, base),
    images: modelImages(model, base),
    clips: modelClips(model, base),
  };
}

/** /api/images.json: every image in the archive. */
export function imagesIndex(data: SiteData, base: ApiBase) {
  const images = generatedModels(data, "image").flatMap((m) => modelImages(m, base));
  return { generated_at: data.generated_at, count: images.length, images };
}

/** /api/audio.json: every clip in the sound archive. */
export function audioIndex(data: SiteData, base: ApiBase) {
  const clips = generatedModels(data, "audio").flatMap((m) => modelClips(m, base));
  return { generated_at: data.generated_at, count: clips.length, clips };
}
