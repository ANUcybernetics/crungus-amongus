import { describe, expect, it } from "vitest";

import {
  clipPositions,
  clipSliders,
  clipWeightsFor,
  frameForSigma,
  nearestKeys,
  type ClipComponent,
  type ClipEigenData,
} from "../src/lib/eigen";

const STEPS = 7;
const SPAN = 3;

function component(overrides: Partial<ClipComponent> = {}): ClipComponent {
  return {
    sigma: 4,
    stability: 0.95,
    frames: null,
    variance: 0.1,
    name: null,
    positive: [],
    negative: [],
    ...overrides,
  };
}

function data(overrides: Partial<ClipEigenData> = {}): ClipEigenData {
  return {
    space: "ViT-bigG-14/laion2b_s39b_b160k",
    image_count: 4,
    stability_threshold: 0.7,
    stability_splits: 8,
    filmstrip_steps: STEPS,
    sigma_span: SPAN,
    components: [component(), component({ stability: 0.4 })],
    text_axis: {
      ...component(),
      prompt: "crungus",
      similarity_mean: 0.22,
      similarity_sigma: 0.03,
      stability: 1,
    },
    coefficients: {
      "a/p/0.avif": [0, 0],
      "a/p/1.avif": [1, 0],
      "b/p/0.avif": [-2, 3],
      // the same point as a/p/0 in the components, and only there
      "c/p/0.avif": [0, 0],
    },
    text_coefficients: {
      "a/p/0.avif": 0,
      "a/p/1.avif": 2,
      "b/p/0.avif": -1,
      "c/p/0.avif": -3,
    },
    ...overrides,
  };
}

describe("frameForSigma", () => {
  it("is monotone and clamped to the strip", () => {
    const indices = Array.from({ length: 401 }, (_, i) =>
      frameForSigma(-2 * SPAN + (i * 4 * SPAN) / 400, STEPS, SPAN),
    );
    expect(indices).toEqual(indices.toSorted((a, b) => a - b));
    expect(Math.min(...indices)).toBe(0);
    expect(Math.max(...indices)).toBe(STEPS - 1);
  });

  it("puts the mean crungus at the centre frame", () => {
    expect(frameForSigma(0, STEPS, SPAN)).toBe(3);
    expect(frameForSigma(-SPAN, STEPS, SPAN)).toBe(0);
    expect(frameForSigma(SPAN, STEPS, SPAN)).toBe(STEPS - 1);
  });

  it("holds on the end frame past the rendered range", () => {
    expect(frameForSigma(-99, STEPS, SPAN)).toBe(0);
    expect(frameForSigma(99, STEPS, SPAN)).toBe(STEPS - 1);
  });

  it("agrees with the pipeline on each whole-sigma step", () => {
    // frame_offsets() in eigen_clip.py: −3σ … +3σ, one frame per σ
    expect([-3, -2, -1, 0, 1, 2, 3].map((p) => frameForSigma(p, STEPS, SPAN))).toEqual([
      0, 1, 2, 3, 4, 5, 6,
    ]);
  });
});

describe("clipSliders", () => {
  it("leads with the supervised axis and numbers the components after it", () => {
    const sliders = clipSliders(data());
    expect(sliders.map((s) => s.number)).toEqual([null, 1, 2]);
    expect(sliders[0]!.name).toBe("crungus-ness");
    expect(sliders[0]!.axis.stability).toBe(1);
  });
});

describe("nearestKeys", () => {
  const positions = clipPositions(data());

  it("puts every slider in the same row, crungus-ness first", () => {
    expect(positions.width).toBe(3);
    expect(positions.values.slice(0, 3)).toEqual(new Float32Array([0, 0, 0]));
    expect(positions.values.slice(3, 6)).toEqual(new Float32Array([2, 1, 0]));
  });

  it("finds an image at its own coordinates first", () => {
    expect(nearestKeys(positions, clipWeightsFor(data(), "b/p/0.avif"), 1)).toEqual(["b/p/0.avif"]);
  });

  it("orders by distance across every slider at once", () => {
    expect(nearestKeys(positions, [0, 0, 0], 3)).toEqual([
      "a/p/0.avif",
      "a/p/1.avif",
      "c/p/0.avif",
    ]);
  });

  it("separates two images that differ only in crungus-ness", () => {
    expect(nearestKeys(positions, [2, 0, 0], 1)).toEqual(["a/p/1.avif"]);
    expect(nearestKeys(positions, [-3, 0, 0], 1)).toEqual(["c/p/0.avif"]);
  });

  it("never returns more than the archive holds", () => {
    expect(nearestKeys(positions, [0, 0, 0], 99)).toHaveLength(4);
  });
});

describe("clipWeightsFor", () => {
  it("reads an image's position off both coefficient tables", () => {
    expect(clipWeightsFor(data(), "b/p/0.avif")).toEqual([-1, -2, 3]);
  });

  it("falls back to the mean for a key the archive does not hold", () => {
    expect(clipWeightsFor(data(), "gone.avif")).toEqual([0]);
  });
});
