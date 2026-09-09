// Finding a thumbnail in the atlas sprite, and fetching the tile it sits on.
//
// `crungus sprite` lays the corpus out in key order across tiles of at most
// 4096 px square — one sheet for the whole archive would be a texture no phone
// will decode — so a key resolves to a tile index and a position within it,
// and a page loads only the tiles it is about to draw.

export interface SpriteIndex {
  cell_px: number;
  keys: string[];
  tiles?: string[]; // tile file names, in order
  tile_cols?: number; // cells across a tile
  tile_cells?: number; // cells in a full tile
  cols?: number; // the pre-tiling layout: cells across the single sheet
}

export interface SpriteCell {
  tile: number;
  x: number;
  y: number;
}

const LEGACY_SHEET = "sprite.webp";

/** The tile file names, relative to the atlas directory. */
export function tileNames(index: SpriteIndex): string[] {
  return index.tiles ?? [LEGACY_SHEET];
}

/** Look a key up by image key; undefined for a key that is not on the sheet.
 *
 * A payload written before tiling has no tile geometry, only `cols` and one
 * unbounded sheet — an infinite tile, which is what the arithmetic below
 * degrades to.
 */
export function cellFinder(index: SpriteIndex): (key: string) => SpriteCell | undefined {
  const position = new Map(index.keys.map((key, i) => [key, i]));
  const cols = index.tile_cols ?? index.cols ?? 1;
  const perTile = index.tile_cells ?? Infinity;
  return (key) => {
    const i = position.get(key);
    if (i === undefined) return undefined;
    const within = i % perTile;
    return {
      tile: Math.floor(i / perTile),
      x: (within % cols) * index.cell_px,
      y: Math.floor(within / cols) * index.cell_px,
    };
  };
}

/** Sprite tiles fetched on demand, with a callback when one arrives. */
export class TileLoader {
  private readonly loaded = new Map<number, HTMLImageElement>();
  private readonly started = new Set<number>();

  constructor(
    private readonly names: string[],
    private readonly base: string,
    private readonly onLoad: (tile: number) => void,
  ) {}

  /** The tile if it is here; otherwise undefined, and a fetch begins. */
  get(tile: number): HTMLImageElement | undefined {
    const ready = this.loaded.get(tile);
    if (ready !== undefined) return ready;
    const name = this.names[tile];
    if (name === undefined || this.started.has(tile)) return undefined;
    this.started.add(tile);
    const image = new Image();
    image.crossOrigin = "anonymous"; // the eigen page reads these pixels back
    image.src = `${this.base}/${name}`;
    void image
      .decode()
      .then(() => {
        this.loaded.set(tile, image);
        this.onLoad(tile);
      })
      // a tile that will not decode stays marked started, so a failure degrades
      // to blank cells rather than a request on every redraw
      .catch(() => {});
    return undefined;
  }
}
