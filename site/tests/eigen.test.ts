import { describe, expect, it } from "vitest";

import {
  decodeSheet,
  modelSlug,
  reconstruct,
  tileChannels,
  type EigenComponent,
} from "../src/lib/eigen";

const SIDE = 2;

function component(overrides: Partial<EigenComponent> = {}): EigenComponent {
  return {
    variance: 0.5,
    scale: 127 / 255, // a byte step of 1 moves a pixel by exactly 1
    sigma: 1,
    name: null,
    positive: [],
    negative: [],
    ...overrides,
  };
}

// a sheet of two tiles: the mean (all 100) and one component that adds to the
// red channel on the first pixel (byte 129) and subtracts on the last (127)
function sheet(): Uint8ClampedArray {
  const width = SIDE * 2;
  const rgba = new Uint8ClampedArray(width * SIDE * 4);
  for (let y = 0; y < SIDE; y++) {
    for (let x = 0; x < width; x++) {
      const i = (y * width + x) * 4;
      const inMean = x < SIDE;
      rgba.set(inMean ? [100, 100, 100, 255] : [128, 128, 128, 255], i);
    }
  }
  rgba[(0 * width + SIDE) * 4] = 129; // tile 1, pixel (0,0), red
  rgba[(1 * width + SIDE + 1) * 4] = 127; // tile 1, pixel (1,1), red
  return rgba;
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
    const components = [component({ sigma: 10 })];
    const decoded = decodeSheet(sheet(), SIDE * 2, SIDE, components);
    const out = new Uint8ClampedArray(SIDE * SIDE * 4);
    reconstruct(decoded, components, [0], out);
    expect([...out]).toEqual(
      Array.from({ length: SIDE * SIDE }, () => [100, 100, 100, 255]).flat(),
    );
    reconstruct(decoded, components, [2], out);
    expect(out[0]).toBe(120); // + 2σ × 1
    expect(out[1]).toBe(100);
    expect(out[12]).toBe(80); // − 2σ × 1
  });

  it("clamps to the byte range", () => {
    const components = [component({ sigma: 1000 })];
    const decoded = decodeSheet(sheet(), SIDE * 2, SIDE, components);
    const out = new Uint8ClampedArray(SIDE * SIDE * 4);
    reconstruct(decoded, components, [1], out);
    expect(out[0]).toBe(255);
    expect(out[12]).toBe(0);
  });

  it("reads the model slug off an image key", () => {
    expect(modelSlug("kuprel--min-dalle/crungus/3.avif")).toBe("kuprel--min-dalle");
  });
});
