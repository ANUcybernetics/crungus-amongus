// Pure pieces of the mosaic wall (pages/display.astro): the tile payload the
// page fetches, the shuffle bag that orders images, tiles and clips, and the
// cells an opened tile covers and ripples into. The grid's shape is the
// stylesheet's job.
import { generatedModels, releaseYear } from "./models";
import type { ImageRef, SiteData } from "./schema";

export interface MosaicImage {
  srcset: string; // every served width, for a grid tile
  full: string; // the bucket original, for single mode
  page: string; // the image's permalink, which a tile links to
}

export interface MosaicPrompt {
  prompt: string;
  images: MosaicImage[];
}

export interface MosaicModel {
  slug: string;
  owner: string;
  name: string;
  year: string;
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

/** Group every image under its model and prompt. */
export function mosaicData(data: SiteData, image: (ref: ImageRef) => MosaicImage): MosaicData {
  const models = generatedModels(data, "image")
    .map((m) => ({
      slug: m.slug,
      owner: m.owner,
      name: m.name,
      year: releaseYear(m),
      prompts: m.prompts
        .map((p) => ({
          prompt: p.prompt,
          images: p.images.map((i) => image(i)),
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

/** The tiles a tile's image shares a model and prompt with, itself left out. */
export function relatives(tile: Tile): Tile[] {
  const images = tile.model.prompts.find((p) => p.prompt === tile.prompt)?.images ?? [];
  return images
    .filter((image) => image.page !== tile.page)
    .map((image) => ({ ...image, model: tile.model, prompt: tile.prompt }));
}

/** A square block of cells on a cols × rows grid, by its top-left cell. */
export interface Block {
  col: number;
  row: number;
  span: number;
}

const clamp = (n: number, lo: number, hi: number): number => Math.min(hi, Math.max(lo, n));

/** The block of up to `span` cells a side that a tapped cell opens into: centred
 * on it where the grid allows, pushed back inside where it would overhang. */
export function openBlock(cell: number, cols: number, rows: number, span: number): Block {
  const side = Math.max(1, Math.min(span, cols, rows));
  const col = cell % cols;
  const row = Math.floor(cell / cols);
  const back = Math.floor(side / 2);
  return {
    col: clamp(col - back, 0, cols - side),
    row: clamp(row - back, 0, rows - side),
    span: side,
  };
}

/** The cells inside `block`, row by row. */
export function blockCells(block: Block, cols: number): number[] {
  const cells: number[] = [];
  for (let r = block.row; r < block.row + block.span; r++) {
    for (let c = block.col; c < block.col + block.span; c++) cells.push(r * cols + c);
  }
  return cells;
}

/** The cells within `rings` of `block` but outside it, nearest `origin` first,
 * so changing them in order spreads outward from the tapped cell. */
export function ringCells(
  block: Block,
  rings: number,
  origin: number,
  cols: number,
  rows: number,
): number[] {
  const ox = origin % cols;
  const oy = Math.floor(origin / cols);
  const cells: [number, number][] = [];
  for (let r = block.row - rings; r < block.row + block.span + rings; r++) {
    for (let c = block.col - rings; c < block.col + block.span + rings; c++) {
      if (r < 0 || c < 0 || r >= rows || c >= cols) continue;
      const inside =
        r >= block.row &&
        r < block.row + block.span &&
        c >= block.col &&
        c < block.col + block.span;
      if (!inside) cells.push([r * cols + c, Math.hypot(c - ox, r - oy)]);
    }
  }
  return cells.toSorted((a, b) => a[1] - b[1]).map(([cell]) => cell);
}
