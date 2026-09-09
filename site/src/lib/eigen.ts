// The eigencrungi widget's arithmetic, kept pure so it can be tested.
//
// The pipeline's `crungus eigen` ships a sheet of side×side tiles — the mean
// crungus followed by one tile per principal component, quantised to bytes
// centred on 128 — plus eigen.json describing each component. Reconstruction
// is the eigenfaces sum: mean + Σ (weight × σ) × component, in pixel space.

export interface EigenComponent {
  variance: number; // share of total variance, 0–1
  scale: number; // dequantisation: value = scale × (byte − 128) / 127
  sigma: number; // standard deviation of the coefficient across the archive
  name: string | null; // hand-given, or null to show by number
  positive: string[]; // image keys at the + extreme
  negative: string[]; // image keys at the − extreme
}

export interface EigenData {
  side: number;
  image_count: number;
  components: EigenComponent[];
  coefficients: Record<string, number[]>; // per image, in σ units
}

export interface EigenBasis {
  mean: Float32Array; // RGB bytes as floats, side²×3
  basis: Float32Array[]; // per component, RGB deltas in byte units per unit coefficient
}

/** Pull one side×side RGB tile out of the sheet's RGBA pixels. */
export function tileChannels(
  rgba: Uint8ClampedArray,
  sheetWidth: number,
  side: number,
  tile: number,
): Float32Array {
  const out = new Float32Array(side * side * 3);
  for (let y = 0; y < side; y++) {
    for (let x = 0; x < side; x++) {
      const from = (y * sheetWidth + tile * side + x) * 4;
      const to = (y * side + x) * 3;
      out[to] = rgba[from]!;
      out[to + 1] = rgba[from + 1]!;
      out[to + 2] = rgba[from + 2]!;
    }
  }
  return out;
}

/** Decode the sheet into the mean and the dequantised components. */
export function decodeSheet(
  rgba: Uint8ClampedArray,
  sheetWidth: number,
  side: number,
  components: EigenComponent[],
): EigenBasis {
  const mean = tileChannels(rgba, sheetWidth, side, 0);
  const basis = components.map((component, j) => {
    const tile = tileChannels(rgba, sheetWidth, side, j + 1);
    // the pipeline's rows were pixels / 255, so a unit coefficient moves a
    // pixel by 255 × component
    const factor = (255 * component.scale) / 127;
    for (let i = 0; i < tile.length; i++) tile[i] = (tile[i]! - 128) * factor;
    return tile;
  });
  return { mean, basis };
}

/** mean + Σ weightₖ σₖ componentₖ, written as opaque RGBA into `out`. */
export function reconstruct(
  { mean, basis }: EigenBasis,
  components: EigenComponent[],
  weights: number[],
  out: Uint8ClampedArray,
): void {
  const pixels = mean.length;
  const scaled = new Float32Array(pixels);
  scaled.set(mean);
  for (let j = 0; j < basis.length; j++) {
    const c = (weights[j] ?? 0) * components[j]!.sigma;
    if (c === 0) continue;
    const tile = basis[j]!;
    for (let i = 0; i < pixels; i++) scaled[i] = scaled[i]! + c * tile[i]!;
  }
  for (let i = 0, o = 0; i < pixels; i += 3, o += 4) {
    out[o] = scaled[i]!;
    out[o + 1] = scaled[i + 1]!;
    out[o + 2] = scaled[i + 2]!;
    out[o + 3] = 255;
  }
}

/** "owner/name" for an image key's model slug ("owner--name/prompt/0.avif"). */
export function modelSlug(key: string): string {
  return key.slice(0, key.indexOf("/"));
}
