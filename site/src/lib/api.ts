// Shapes of the static JSON API under /api/. Unlike models.json (the internal
// contract, keyed relative to the bucket) these are for outside consumers, so
// every URL is absolute and each item carries its model and prompt.
import { clipCount, generatedModels, imageCount, meshedImages, videoCount } from "./models";
import { itemRoute } from "./permalink";
import type { ModelEntry, SiteData } from "./schema";

export interface ApiImage {
  url: string;
  page: string; // its permalink on the site
  model: string;
  prompt: string;
  mesh?: string; // GLB, only for the images Meshy has reconstructed
}

export interface ApiMesh {
  url: string; // GLB: meshopt geometry, WebP textures
  image: string; // the archive image it was reconstructed from
  page: string; // the image's permalink, which opens the mesh
  model: string;
  prompt: string;
}

export interface ApiClip {
  opus: string;
  m4a: string;
  page: string;
  model: string;
  prompt: string;
}

export interface ApiVideo {
  mp4: string; // H.264, with the model's soundtrack where it made one
  poster: string; // JPEG of the first frame
  page: string;
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

function itemPage(key: string, base: ApiBase): string {
  return new URL(itemRoute(key), base.site).href;
}

export function modelImages(model: ModelEntry, base: ApiBase): ApiImage[] {
  return model.prompts.flatMap((p) =>
    p.images.map((i) => ({
      url: `${base.media}/${i.key}`,
      page: itemPage(i.key, base),
      model: model.slug,
      prompt: p.prompt,
      ...(i.mesh !== undefined && { mesh: `${base.media}/${i.mesh}` }),
    })),
  );
}

export function modelClips(model: ModelEntry, base: ApiBase): ApiClip[] {
  return model.prompts.flatMap((p) =>
    p.clips.map((c) => ({
      opus: `${base.media}/${c.opus}`,
      m4a: `${base.media}/${c.m4a}`,
      page: itemPage(c.opus, base),
      model: model.slug,
      prompt: p.prompt,
    })),
  );
}

export function modelVideos(model: ModelEntry, base: ApiBase): ApiVideo[] {
  return model.prompts.flatMap((p) =>
    p.videos.map((v) => ({
      mp4: `${base.media}/${v.mp4}`,
      poster: `${base.media}/${v.poster}`,
      page: itemPage(v.mp4, base),
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
    videos: videoCount(model),
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
    videos: modelVideos(model, base),
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

/** /api/videos.json: every clip in the video archive. */
export function videosIndex(data: SiteData, base: ApiBase) {
  const videos = generatedModels(data, "video").flatMap((m) => modelVideos(m, base));
  return { generated_at: data.generated_at, count: videos.length, videos };
}

/** /api/meshes.json: every mesh, with the image it was made from. */
export function meshesIndex(data: SiteData, base: ApiBase) {
  const meshes: ApiMesh[] = meshedImages(data).map(({ model, prompt, image }) => ({
    url: `${base.media}/${image.mesh}`,
    image: `${base.media}/${image.key}`,
    page: itemPage(image.key, base),
    model: model.slug,
    prompt: prompt.prompt,
  }));
  return { generated_at: data.generated_at, count: meshes.length, meshes };
}
