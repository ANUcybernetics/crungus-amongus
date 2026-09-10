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

// ---------------------------------------------------------------------------
// The semantic basis: PCA in CLIP embedding space (crungus eigen --space clip).
//
// An axis in a 1280-d embedding space is not a picture, so nothing is
// reconstructed here. Each retained axis instead ships a filmstrip Kandinsky
// 2.2's decoder rendered along it, and the archive answers for itself through
// the nearest real images to the current slider state.

/** One semantic slider: its scale, how well it holds, and its rendered strip. */
export interface ClipAxis {
  sigma: number; // standard deviation of the coefficient across the archive
  stability: number; // mean |cos| against a disjoint-half resample, 0–1
  frames: string[] | null; // filmstrip keys, −σ to +σ; null when not rendered
  positive: string[]; // image keys at the + extreme
  negative: string[]; // image keys at the − extreme
}

export interface ClipComponent extends ClipAxis {
  variance: number; // share of total variance, 0–1
  name: string | null; // hand-given, or null to show by number
}

export interface ClipTextAxis extends ClipAxis {
  prompt: string;
  similarity_mean: number; // cosine with the archive, before standardising
  similarity_sigma: number;
}

export interface ClipEigenData {
  space: string; // the checkpoint the embeddings came from
  image_count: number;
  stability_threshold: number;
  stability_splits: number;
  filmstrip_steps: number;
  sigma_span: number;
  components: ClipComponent[];
  text_axis: ClipTextAxis;
  coefficients: Record<string, number[]>; // per image, in σ units
  text_coefficients: Record<string, number>; // per image, in σ units
}

/** A semantic slider: its axis, its heading, and its 1-based number. */
export interface ClipSlider {
  axis: ClipAxis;
  name: string | null;
  number: number | null; // null for the supervised crungus-ness axis
}

/** The page's semantic sliders in order: crungus-ness first, then components. */
export function clipSliders(data: ClipEigenData): ClipSlider[] {
  return [
    { axis: data.text_axis, name: `${data.text_axis.prompt}-ness`, number: null },
    ...data.components.map((component, j) => ({
      axis: component,
      name: component.name,
      number: j + 1,
    })),
  ];
}

/** The filmstrip frame nearest a slider position in σ.
 *
 * Monotone in `position` and clamped to the strip, so dragging past the
 * rendered range holds on the end frame rather than wrapping. Mirrors
 * eigen_clip.frame_for_sigma in the pipeline.
 */
export function frameForSigma(position: number, steps: number, span: number): number {
  const index = Math.round(((position + span) * (steps - 1)) / (2 * span));
  return Math.max(0, Math.min(steps - 1, index));
}

/** Every image's position on every slider, as one flat row-major matrix.
 *
 * Column 0 is crungus-ness and the rest are the components, all in σ, which
 * is what makes a plain Euclidean distance across them meaningful.
 */
export interface ClipPositions {
  keys: string[];
  width: number;
  values: Float32Array;
}

export function clipPositions(data: ClipEigenData): ClipPositions {
  const keys = Object.keys(data.coefficients);
  const width = data.components.length + 1;
  const values = new Float32Array(keys.length * width);
  keys.forEach((key, i) => {
    values[i * width] = data.text_coefficients[key] ?? 0;
    const row = data.coefficients[key]!;
    for (let j = 0; j < row.length; j++) values[i * width + j + 1] = row[j]!;
  });
  return { keys, width, values };
}

/** The `count` archive images closest to `weights`, nearest first.
 *
 * Distance is Euclidean over every slider at once, in σ units — so unlike the
 * filmstrip, which follows one axis, this is where the whole slider state
 * actually lands among the real crungi.
 */
export function nearestKeys(
  { keys, width, values }: ClipPositions,
  weights: readonly number[],
  count: number,
): string[] {
  const best: { key: string; distance: number }[] = [];
  for (let i = 0; i < keys.length; i++) {
    let sum = 0;
    for (let j = 0; j < width; j++) {
      const delta = values[i * width + j]! - (weights[j] ?? 0);
      sum += delta * delta;
    }
    // keep the running top `count` rather than sorting nineteen thousand rows
    // on every slider move
    if (best.length < count || sum < best.at(-1)!.distance) {
      const entry = { key: keys[i]!, distance: sum };
      const at = best.findIndex((e) => sum < e.distance);
      best.splice(at === -1 ? best.length : at, 0, entry);
      if (best.length > count) best.pop();
    }
  }
  return best.map((e) => e.key);
}

/** One real image's position on every semantic slider, in σ units. */
export function clipWeightsFor(data: ClipEigenData, key: string): number[] {
  return [data.text_coefficients[key] ?? 0, ...(data.coefficients[key] ?? [])];
}
