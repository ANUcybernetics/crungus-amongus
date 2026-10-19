// Pure pieces of the mosaic wall (pages/display.astro): the tile payload the
// page fetches and the shuffle bag that orders images, tiles and clips. The
// grid's shape is the stylesheet's job.
import { generatedModels } from "./models";
import type { SiteData } from "./schema";

export interface MosaicImage {
  srcset: string; // the built thumbnails, for a grid tile
  full: string; // the bucket original, for single mode
}

export interface MosaicPrompt {
  prompt: string;
  images: MosaicImage[];
}

export interface MosaicModel {
  slug: string;
  owner: string;
  name: string;
  prompts: MosaicPrompt[];
}

/** /display/tiles.json: every image model with the thumbnails it can show. */
export interface MosaicData {
  models: MosaicModel[];
}

export interface Tile extends MosaicImage {
  model: MosaicModel;
  prompt: string;
}

/** Group every synced image under its model and prompt. */
export function mosaicData(data: SiteData, image: (key: string) => MosaicImage | null): MosaicData {
  const models = generatedModels(data, "image")
    .map((m) => ({
      slug: m.slug,
      owner: m.owner,
      name: m.name,
      prompts: m.prompts
        .map((p) => ({
          prompt: p.prompt,
          images: p.images.map((i) => image(i.key)).filter((i): i is MosaicImage => i !== null),
        }))
        .filter((p) => p.images.length > 0),
    }))
    .filter((m) => m.prompts.length > 0);
  return { models };
}

/** Every tile the wall may show: one model's if `slug` names one, else all. */
export function tilesFor(data: MosaicData, slug?: string): Tile[] {
  const chosen = data.models.filter((m) => m.slug === slug);
  return (chosen.length > 0 ? chosen : data.models).flatMap((model) =>
    model.prompts.flatMap((p) => p.images.map((image) => ({ ...image, model, prompt: p.prompt }))),
  );
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
