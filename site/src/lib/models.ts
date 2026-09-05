// Pure helpers over the site data contract. Keep side-effect-free so tests
// and scripts can reuse them; the data-binding layer (data.ts) imports the JSON.
import type { ClipRef, Modality, ModelEntry, PromptOutputs, SiteData } from "./schema";

/** Models that produced at least one output, in timeline order; optionally one modality. */
export function generatedModels(data: SiteData, modality?: Modality): ModelEntry[] {
  return data.models.filter(
    (m) => outputCount(m) > 0 && (modality === undefined || m.modality === modality),
  );
}

/** Models that were attempted but produced nothing — part of the story. */
export function failedModels(data: SiteData, modality?: Modality): ModelEntry[] {
  return data.models.filter(
    (m) =>
      outputCount(m) === 0 &&
      m.status !== "pending" &&
      (modality === undefined || m.modality === modality),
  );
}

export function imageCount(model: ModelEntry): number {
  return model.prompts.reduce((n, p) => n + p.images.length, 0);
}

export function clipCount(model: ModelEntry): number {
  return model.prompts.reduce((n, p) => n + p.clips.length, 0);
}

export function outputCount(model: ModelEntry): number {
  return imageCount(model) + clipCount(model);
}

export function promptBySlug(model: ModelEntry, promptSlug: string): PromptOutputs | undefined {
  return model.prompts.find((p) => p.prompt_slug === promptSlug);
}

/** Overall crungus-ness: the max consistency across prompts (a model "has a
 * crungus" if either prompt summons a stable creature). */
export function crungusness(model: ModelEntry): number | null {
  const scores = model.prompts.map((p) => p.consistency).filter((s): s is number => s !== null);
  return scores.length ? Math.max(...scores) : null;
}

export function releaseYear(model: ModelEntry): string {
  return model.release_date?.slice(0, 4) ?? "undated";
}

/** A representative thumbnail: first image of the bare-word prompt, else first anywhere. */
export function coverImage(model: ModelEntry): string | null {
  const bare = promptBySlug(model, "crungus");
  return bare?.images[0]?.key ?? model.prompts.flatMap((p) => p.images)[0]?.key ?? null;
}

/** A representative clip, by the same rule as coverImage. */
export function coverClip(model: ModelEntry): ClipRef | null {
  const bare = promptBySlug(model, "crungus");
  return bare?.clips[0] ?? model.prompts.flatMap((p) => p.clips)[0] ?? null;
}

export function byCrungusness(models: ModelEntry[]): ModelEntry[] {
  return models.toSorted((a, b) => (crungusness(b) ?? -1) - (crungusness(a) ?? -1));
}

/** Timeline order: release date ascending (contract order), undated last. */
export function byTimeline(models: ModelEntry[]): ModelEntry[] {
  return models.toSorted((a, b) => {
    if (a.release_date === b.release_date) return a.slug.localeCompare(b.slug);
    if (a.release_date === null) return 1;
    if (b.release_date === null) return -1;
    return a.release_date < b.release_date ? -1 : 1;
  });
}

/** Dated models grouped by release year, ascending; undated under "undated". */
export function byYear(models: ModelEntry[]): [string, ModelEntry[]][] {
  const groups = new Map<string, ModelEntry[]>();
  for (const model of byTimeline(models)) {
    const year = releaseYear(model);
    groups.set(year, [...(groups.get(year) ?? []), model]);
  }
  return [...groups.entries()];
}

export interface YearSample {
  year: string;
  model: ModelEntry;
  key: string;
}

/** One image per year for the hero filmstrip: the year's most *typical*
 * crungus — the image with the highest mean CLIP similarity to every other
 * image from that release year (computed by the pipeline) — so the strip
 * shows how the word's dominant creature mutates era by era. */
export function timelineSample(models: ModelEntry[]): YearSample[] {
  const samples: YearSample[] = [];
  for (const [year, group] of byYear(models)) {
    if (year === "undated") continue;
    const images = group.flatMap((model) =>
      model.prompts.flatMap((p) =>
        p.images
          .filter((i) => i.typicality !== null)
          .map((i) => ({ model, key: i.key, typicality: i.typicality! })),
      ),
    );
    if (images.length === 0) continue;
    const best = images.reduce((a, b) => (b.typicality > a.typicality ? b : a));
    samples.push({ year, model: best.model, key: best.key });
  }
  return samples;
}
