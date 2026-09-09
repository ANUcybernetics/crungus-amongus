import { describe, expect, it } from "vitest";

import {
  decodeSheet,
  modelSlug,
  reconstruct,
  sliders,
  tileChannels,
  weightsFor,
  type EigenComponent,
  type EigenData,
  type EigenTextAxis,
} from "../src/lib/eigen";

const SIDE = 2;

function component(overrides: Partial<EigenComponent> = {}): EigenComponent {
  return {
    tile: 1,
    variance: 0.5,
    scale: 127 / 255, // a byte step of 1 moves a pixel by exactly 1
    sigma: 1,
    stability: 0.9,
    name: null,
    positive: [],
    negative: [],
    ...overrides,
  };
}

function textAxis(overrides: Partial<EigenTextAxis> = {}): EigenTextAxis {
  return {
    ...component(),
    prompt: "crungus",
    vector: [1],
    similarity_mean: 0.22,
    similarity_sigma: 0.03,
    stability: 1,
    ...overrides,
  };
}

// a sheet of `tiles` tiles: the mean (all 100) and then components that add to
// the red channel on the first pixel (byte 129) and subtract on the last (127)
function sheet(tiles = 2): Uint8ClampedArray {
  const width = SIDE * tiles;
  const rgba = new Uint8ClampedArray(width * SIDE * 4);
  for (let y = 0; y < SIDE; y++) {
    for (let x = 0; x < width; x++) {
      const i = (y * width + x) * 4;
      rgba.set(x < SIDE ? [100, 100, 100, 255] : [128, 128, 128, 255], i);
    }
  }
  for (let tile = 1; tile < tiles; tile++) {
    rgba[(0 * width + tile * SIDE) * 4] = 129; // pixel (0,0), red
    rgba[(1 * width + tile * SIDE + 1) * 4] = 127; // pixel (1,1), red
  }
  return rgba;
}

function data(overrides: Partial<EigenData> = {}): EigenData {
  return {
    side: SIDE,
    image_count: 2,
    stability_threshold: 0.7,
    stability_splits: 8,
    components: [component({ tile: 1 }), component({ tile: 2, stability: 0.3 })],
    coefficients: { "a--b/crungus/0.avif": [1, -2] },
    ...overrides,
  };
}

describe("eigen arithmetic", () => {
  it("cuts tiles out of the sheet", () => {
    const mean = tileChannels(sheet(), SIDE * 2, SIDE, 0);
    expect([...mean]).toEqual(Array(SIDE * SIDE * 3).fill(100));
  });

  it("dequantises components around 128", () => {
    const { basis } = decodeSheet(sheet(), SIDE * 2, SIDE, [component()]);
    expect(basis[0]![0]).toBeCloseTo(1);
    expect(basis[0]![9]).toBeCloseTo(-1);
    expect(basis[0]![1]).toBeCloseTo(0);
  });

  it("reconstructs the mean at zero weight and moves with the weight", () => {
    const axes = [component({ sigma: 10 })];
    const decoded = decodeSheet(sheet(), SIDE * 2, SIDE, axes);
    const out = new Uint8ClampedArray(SIDE * SIDE * 4);
    reconstruct(decoded, axes, [0], out);
    expect([...out]).toEqual(
      Array.from({ length: SIDE * SIDE }, () => [100, 100, 100, 255]).flat(),
    );
    reconstruct(decoded, axes, [2], out);
    expect(out[0]).toBe(120); // + 2σ × 1
    expect(out[1]).toBe(100);
    expect(out[12]).toBe(80); // − 2σ × 1
  });

  it("clamps to the byte range", () => {
    const axes = [component({ sigma: 1000 })];
    const decoded = decodeSheet(sheet(), SIDE * 2, SIDE, axes);
    const out = new Uint8ClampedArray(SIDE * SIDE * 4);
    reconstruct(decoded, axes, [1], out);
    expect(out[0]).toBe(255);
    expect(out[12]).toBe(0);
  });

  it("reads the model slug off an image key", () => {
    expect(modelSlug("kuprel--min-dalle/crungus/3.avif")).toBe("kuprel--min-dalle");
  });
});

describe("the supervised axis", () => {
  const payload = data({
    components: [component({ tile: 1, sigma: 10 })],
    text_axis: textAxis({ tile: 2, sigma: 5 }),
    coefficients: { "a--b/crungus/0.avif": [1.5] },
    text_coefficients: { "a--b/crungus/0.avif": -0.5 },
  });

  it("leads the numbered components", () => {
    const list = sliders(payload);
    expect(list.map((s) => s.number)).toEqual([null, 1]);
    expect(list[0]!.name).toBe("crungus-ness");
    expect(list[0]!.axis.tile).toBe(2);
    expect(list[0]!.axis.stability).toBe(1);
  });

  it("moves the reconstruction on its own tile and σ", () => {
    const axes = sliders(payload).map((s) => s.axis);
    const decoded = decodeSheet(sheet(3), SIDE * 3, SIDE, axes);
    const out = new Uint8ClampedArray(SIDE * SIDE * 4);
    reconstruct(decoded, axes, [0, 0], out);
    expect(out[0]).toBe(100);
    reconstruct(decoded, axes, [2, 0], out);
    expect(out[0]).toBe(110); // + 2 × 5σ × 1, the supervised axis alone
    reconstruct(decoded, axes, [2, 1], out);
    expect(out[0]).toBe(120); // and the component adds its own 1 × 10σ
  });

  it("puts a real image on every slider, crungus-ness first", () => {
    expect(weightsFor(payload, "a--b/crungus/0.avif")).toEqual([-0.5, 1.5]);
  });

  it("falls back to the numbered components when the payload has no text axis", () => {
    const older = data();
    expect(sliders(older).map((s) => s.number)).toEqual([1, 2]);
    expect(weightsFor(older, "a--b/crungus/0.avif")).toEqual([1, -2]);
  });

  it("lays tiles out after the mean when the payload predates tile indices", () => {
    const older = data();
    // @ts-expect-error — a payload written before axes carried a tile index
    delete older.components[0]!.tile;
    // @ts-expect-error — as above
    delete older.components[1]!.tile;
    expect(sliders(older).map((s) => s.axis.tile)).toEqual([1, 2]);
  });
});

describe("stability", () => {
  it("marks which components survive resampling", () => {
    const list = sliders(data());
    const threshold = data().stability_threshold;
    expect(list.map((s) => s.axis.stability > threshold)).toEqual([true, false]);
  });
});
