// Pure pieces of the mosaic wall (pages/mosaic.astro): the tile payload the
// page fetches, the grid shape for a given stage, and the shuffle bag that
// orders images, tiles and clips.
import { generatedModels } from "./models";
import type { SiteData } from "./schema";

export interface MosaicPrompt {
  prompt: string;
  thumbs: string[]; // site-relative URLs of the built thumbnails
}

export interface MosaicModel {
  slug: string;
  owner: string;
  name: string;
  prompts: MosaicPrompt[];
}

/** /mosaic/tiles.json: every image model with the thumbnails it can show. */
export interface MosaicData {
  models: MosaicModel[];
}

export interface Tile {
  src: string;
  model: MosaicModel;
  prompt: string;
}

/** Group every synced image's thumbnail under its model and prompt. */
export function mosaicData(data: SiteData, thumb: (key: string) => string | null): MosaicData {
  const models = generatedModels(data, "image")
    .map((m) => ({
      slug: m.slug,
      owner: m.owner,
      name: m.name,
      prompts: m.prompts
        .map((p) => ({
          prompt: p.prompt,
          thumbs: p.images.map((i) => thumb(i.key)).filter((url): url is string => url !== null),
        }))
        .filter((p) => p.thumbs.length > 0),
    }))
    .filter((m) => m.prompts.length > 0);
  return { models };
}

/** Every tile the wall may show: one model's if `slug` names one, else all. */
export function tilesFor(data: MosaicData, slug?: string): Tile[] {
  const chosen = data.models.filter((m) => m.slug === slug);
  return (chosen.length > 0 ? chosen : data.models).flatMap((model) =>
    model.prompts.flatMap((p) => p.thumbs.map((src) => ({ src, model, prompt: p.prompt }))),
  );
}

const MAX_COLS = 16;
const MIN_COLS = 3;
const MIN_TILE_PX = 100;

/** Rows and columns of near-square tiles that fill a stage: 16 × 9 on any
 * 16:9 panel from HD up, fewer and larger tiles as the stage narrows. */
export function gridShape(width: number, height: number): { cols: number; rows: number } {
  const cols = Math.min(MAX_COLS, Math.max(MIN_COLS, Math.floor(width / MIN_TILE_PX)));
  const rows = Math.max(1, Math.round(height / (width / cols)));
  return { cols, rows };
}

/** Endless draws from `items` in shuffled order: every item once before any repeats. */
export function shuffleBag<T>(items: readonly T[], random: () => number = Math.random): () => T {
  if (items.length === 0) throw new Error("cannot draw from an empty bag");
  let bag: T[] = [];
  return () => {
    if (bag.length === 0) {
      bag = [...items];
      for (let i = bag.length - 1; i > 0; i--) {
        const j = Math.floor(random() * (i + 1));
        [bag[i], bag[j]] = [bag[j]!, bag[i]!];
      }
    }
    return bag.pop()!;
  };
}
