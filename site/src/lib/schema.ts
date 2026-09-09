// zod mirror of the pipeline's site data contract (pipeline/src/crungus_amongus/site_export.py)
import { z } from "zod";

export const modalitySchema = z.enum(["image", "audio"]);

export const imageRefSchema = z.object({
  key: z.string(), // "<model-slug>/<prompt-slug>/<index>.avif", relative to imageBaseUrl
  atlas: z.tuple([z.number(), z.number()]).nullable(),
  typicality: z.number().nullable(), // mean cos sim to the release year's images
});

// both relative to imageBaseUrl; opus where the browser can play it, m4a otherwise
export const clipRefSchema = z.object({
  opus: z.string(), // "<model-slug>/<prompt-slug>/<index>.opus"
  m4a: z.string(), // "<model-slug>/<prompt-slug>/<index>.m4a"
});

// how the asking went for the images the corpus actually holds
export const attemptsSchema = z.object({
  total: z.number().int(),
  succeeded: z.number().int(),
  refused: z.number().int(), // the provider's own classifier rejected the output
  failed: z.number().int(), // everything else terminal
});

// what the provider's default safety filter did, before it was turned off: a
// dated historical measurement, frozen, not a live statistic. Every model with
// a safety control is now asked with it wide open, so a rate computed today
// would describe our configuration rather than theirs.
export const refusalsSchema = z.object({
  measured_until: z.iso.datetime(),
  asked: z.number().int(),
  refused: z.number().int(),
});

export const promptOutputsSchema = z.object({
  prompt: z.string(),
  prompt_slug: z.string(),
  consistency: z.number().nullable(),
  attempts: attemptsSchema,
  refusals: refusalsSchema,
  images: z.array(imageRefSchema), // image models
  clips: z.array(clipRefSchema), // audio models
});

export const modelEntrySchema = z.object({
  slug: z.string(),
  owner: z.string(),
  name: z.string(),
  modality: modalitySchema,
  version_id: z.string().nullable(),
  description: z.string().nullable(),
  source: z.enum(["collection", "legacy"]),
  is_official: z.boolean(),
  release_date: z.iso.date().nullable(),
  replicate_url: z.url(),
  status: z.enum(["ok", "partial", "failed", "incompatible", "unavailable", "pending"]),
  prompts: z.array(promptOutputsSchema),
  notes: z.string().nullable(),
});

export const siteDataSchema = z.object({
  generated_at: z.iso.datetime(),
  image_base_url: z.url(),
  models: z.array(modelEntrySchema),
});

export type Modality = z.infer<typeof modalitySchema>;
export type ImageRef = z.infer<typeof imageRefSchema>;
export type ClipRef = z.infer<typeof clipRefSchema>;
export type Attempts = z.infer<typeof attemptsSchema>;
export type Refusals = z.infer<typeof refusalsSchema>;
export type PromptOutputs = z.infer<typeof promptOutputsSchema>;
export type ModelEntry = z.infer<typeof modelEntrySchema>;
export type SiteData = z.infer<typeof siteDataSchema>;
