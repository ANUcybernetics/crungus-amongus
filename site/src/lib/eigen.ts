// The eigencrungi widget's arithmetic, kept pure so it can be tested.
//
// The pipeline's `crungus eigen` ships a sheet of side×side tiles — the mean
// crungus, one tile per principal component, then the supervised crungus-ness
// axis, each quantised to bytes centred on 128 — plus eigen.json describing
// them. Reconstruction is the eigenfaces sum: mean + Σ (weight × σ) × axis, in
// pixel space, and the supervised axis joins that sum on the same terms.

/** One slider's direction: a sheet tile plus the units its coefficient is in. */
export interface EigenAxis {
  tile: number; // index into the sheet, 0 being the mean
  scale: number; // dequantisation: value = scale × (byte − 128) / 127
  sigma: number; // standard deviation of the coefficient across the archive
  stability: number; // mean |cos| against a disjoint-half resample, 0–1
  positive: string[]; // image keys at the + extreme
  negative: string[]; // image keys at the − extreme
}

export interface EigenComponent extends EigenAxis {
  variance: number; // share of total variance, 0–1
  name: string | null; // hand-given, or null to show by number
}

/** Every image projected onto the CLIP text embedding of a prompt. */
export interface EigenTextAxis extends EigenAxis {
  prompt: string;
  vector: number[]; // the text embedding itself, the axis's definition
  similarity_mean: number; // cosine with the archive, before standardising
  similarity_sigma: number;
}

export interface EigenData {
  side: number;
  image_count: number;
  stability_threshold: number;
  stability_splits: number;
  components: EigenComponent[];
  coefficients: Record<string, number[]>; // per image, in σ units
  text_axis?: EigenTextAxis;
  text_coefficients?: Record<string, number>; // per image, in σ units
}

export interface EigenBasis {
  mean: Float32Array; // RGB bytes as floats, side²×3
  basis: Float32Array[]; // per axis, RGB deltas in byte units per unit coefficient
}

/** A slider: its direction, its heading, and how to read its coefficient. */
export interface Slider {
  axis: EigenAxis;
  name: string | null; // null renders as "component N"
  number: number | null; // 1-based component number; null for the supervised axis
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

/** Decode the sheet into the mean and one dequantised direction per axis. */
export function decodeSheet(
  rgba: Uint8ClampedArray,
  sheetWidth: number,
  side: number,
  axes: readonly Pick<EigenAxis, "tile" | "scale">[],
): EigenBasis {
  const mean = tileChannels(rgba, sheetWidth, side, 0);
  const basis = axes.map((axis) => {
    const tile = tileChannels(rgba, sheetWidth, side, axis.tile);
    // the pipeline's rows were pixels / 255, so a unit coefficient moves a
    // pixel by 255 × direction
    const factor = (255 * axis.scale) / 127;
    for (let i = 0; i < tile.length; i++) tile[i] = (tile[i]! - 128) * factor;
    return tile;
  });
  return { mean, basis };
}

/** mean + Σ weightₖ σₖ axisₖ, written as opaque RGBA into `out`. */
export function reconstruct(
  { mean, basis }: EigenBasis,
  axes: readonly Pick<EigenAxis, "sigma">[],
  weights: number[],
  out: Uint8ClampedArray,
): void {
  const pixels = mean.length;
  const scaled = new Float32Array(pixels);
  scaled.set(mean);
  for (let j = 0; j < basis.length; j++) {
    const c = (weights[j] ?? 0) * axes[j]!.sigma;
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

/** The page's sliders in order: crungus-ness first, then the components.
 *
 * A payload written before the supervised axis existed has neither a text axis
 * nor tile indices; the tiles were laid out after the mean in component order,
 * which is the fallback here, so an older bucket still renders.
 */
export function sliders(data: EigenData): Slider[] {
  const components = data.components.map((component, j) => ({
    axis: { ...component, tile: component.tile ?? j + 1 },
    name: component.name,
    number: j + 1,
  }));
  const text = data.text_axis;
  if (text === undefined) return components;
  return [
    {
      axis: { ...text, tile: text.tile ?? data.components.length + 1 },
      name: `${text.prompt}-ness`,
      number: null,
    },
    ...components,
  ];
}

/** One real image's position on every slider, in σ units. */
export function weightsFor(data: EigenData, key: string): number[] {
  const components = data.coefficients[key] ?? data.components.map(() => 0);
  if (data.text_axis === undefined) return [...components];
  return [data.text_coefficients?.[key] ?? 0, ...components];
}

/** "owner/name" for an image key's model slug ("owner--name/prompt/0.avif"). */
export function modelSlug(key: string): string {
  return key.slice(0, key.indexOf("/"));
}
