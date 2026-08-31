// Pure helpers over the site data contract. Keep side-effect-free so tests
// and scripts can reuse them; the data-binding layer (data.ts) imports the JSON.
import type { ModelEntry, PromptImages, SiteData } from "./schema";

/** Models that produced at least one image, in timeline order. */
export function generatedModels(data: SiteData): ModelEntry[] {
  return data.models.filter((m) => imageCount(m) > 0);
}

/** Models that were attempted but produced nothing — part of the story. */
export function failedModels(data: SiteData): ModelEntry[] {
  return data.models.filter((m) => imageCount(m) === 0 && m.status !== "pending");
}

export function imageCount(model: ModelEntry): number {
  return model.prompts.reduce((n, p) => n + p.images.length, 0);
}

export function promptBySlug(model: ModelEntry, promptSlug: string): PromptImages | undefined {
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

/** One model per year for the hero filmstrip: the most consistent creature of
 * each year, so the strip shows the same word mutating era by era. */
export function timelineSample(models: ModelEntry[]): ModelEntry[] {
  return byYear(models)
    .filter(([year]) => year !== "undated")
    .map(([, group]) => byCrungusness(group.filter((m) => coverImage(m) !== null))[0])
    .filter((m): m is ModelEntry => m !== undefined);
}
