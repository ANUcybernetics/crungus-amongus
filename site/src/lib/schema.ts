// zod mirror of the pipeline's site data contract (pipeline/src/crungus_amongus/site_export.py)
import { z } from "zod";

export const imageRefSchema = z.object({
  key: z.string(), // "<model-slug>/<prompt-slug>/<index>.avif", relative to imageBaseUrl
  atlas: z.tuple([z.number(), z.number()]).nullable(),
  typicality: z.number().nullable(), // mean cos sim to the release year's images
});

export const promptImagesSchema = z.object({
  prompt: z.string(),
  prompt_slug: z.string(),
  consistency: z.number().nullable(),
  images: z.array(imageRefSchema),
});

export const modelEntrySchema = z.object({
  slug: z.string(),
  owner: z.string(),
  name: z.string(),
  version_id: z.string().nullable(),
  description: z.string().nullable(),
  source: z.enum(["collection", "legacy"]),
  is_official: z.boolean(),
  release_date: z.iso.date().nullable(),
  replicate_url: z.url(),
  status: z.enum(["ok", "partial", "failed", "incompatible", "unavailable", "pending"]),
  prompts: z.array(promptImagesSchema),
  notes: z.string().nullable(),
});

export const siteDataSchema = z.object({
  generated_at: z.iso.datetime(),
  image_base_url: z.url(),
  models: z.array(modelEntrySchema),
});

export type ImageRef = z.infer<typeof imageRefSchema>;
export type PromptImages = z.infer<typeof promptImagesSchema>;
export type ModelEntry = z.infer<typeof modelEntrySchema>;
export type SiteData = z.infer<typeof siteDataSchema>;
