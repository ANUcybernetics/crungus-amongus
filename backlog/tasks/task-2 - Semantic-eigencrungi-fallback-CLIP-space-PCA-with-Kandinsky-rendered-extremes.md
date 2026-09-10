---
id: TASK-2
title: 'Semantic eigencrungi: CLIP-space PCA with Kandinsky-rendered extremes'
status: Done
assignee: []
created_date: '2026-09-09 06:48'
updated_date: '2026-09-10 07:20'
labels:
  - pipeline
  - site
dependencies:
  - TASK-4
  - TASK-5
references:
  - 'https://huggingface.co/kandinsky-community/kandinsky-2-2-decoder'
  - pipeline/src/crungus_amongus/eigen.py
  - pipeline/src/crungus_amongus/analyzer.py
  - pipeline/src/crungus_amongus/bucket_sync.py
priority: high
ordinal: 800
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Why

Semantic eigencrungi: PCA in CLIP image-embedding space, where the components are things like photoreal-versus-illustration rather than brightness and framing, with each component's extremes rendered once by Kandinsky 2.2's decoder, which takes a CLIP image embedding directly.

This is no longer a fallback for the generator task. It is the better idea and should ship first. It decomposes the actual archive rather than a model's guess at it, its components are genuinely semantic, it is exactly reproducible, it ships no model weights to the browser, and the decoder is itself one of the archive's own models — a neater loop than a bespoke GAN. It is also perhaps a tenth of the work, with no in-browser inference runtime.

Measured evidence that the CLIP space is the right one: its top-24 subspace overlap under disjoint-half resampling is 0.821 versus 0.751 for pixel space, and its leading component is semantic rather than a light meter (pixel PC1 correlates with mean brightness at r = 0.996).

## Design

### Embeddings (`crungus eigen --space clip`)

- Kandinsky 2.2's decoder conditions on ViT-bigG-14 CLIP image embeddings (1280-d), not the ViT-B-32-quickgelu (512-d) embeddings `analyzer.py` caches. Re-embed every optimized image with open-clip `ViT-bigG-14` / `laion2b_s39b_b160k` on the local GPU into `state/embeddings-bigg.npz`, keyed like the existing cache. Keep the ViT-B/32 cache for consistency scores and the atlas; do not change them.
- PCA (reuse `eigen.pca`) on the 1280-d embeddings, 24 components, same sign convention, coefficients per image in sigma units.

### Truncate before rendering

Only 2 of 24 CLIP components reproduce above 0.9 under disjoint-half resampling, and the tail is near-degenerate. Rendering 24 filmstrips of which sixteen are sampling noise is wasted generation.

- compute the same per-component stability score this project uses elsewhere, and render filmstrips only for components whose stability exceeds 0.7 — expect roughly 6 to 8 rather than 24. Ship stability for all 24 so the page can show the tail as unnamed.
- also render the supervised crungus-ness axis: the direction of the CLIP text embedding of "crungus", expressed in bigG space. It is perfectly reproducible by construction and is the headline slider on the page.

### Rendering the extremes

- for the mean embedding, each retained component at mean +/- 3 sigma, and 7 steps along each retained component, decode with `kandinsky-community/kandinsky-2-2-decoder` (diffusers, `image_embeds` input, 50 steps, 512 px, fixed seed, empty negative embedding). Three seeds per embedding, keep the median by CLIP similarity to the target so one bad sample does not stand for a direction.
- run locally on the RTX 6000; if diffusers will not install alongside the pipeline's torch, run it as a standalone `uv run --script` with its own inline deps.
- encode to AVIF at 256 px with the existing optimizer settings.

### Output location — do not contaminate the corpus

`sprite.py`, `eigen.py` and `analyzer.py` all glob `optimized_dir.rglob("*.avif")`. Writing Kandinsky's renders anywhere under `data/optimized/` would silently feed them into the atlas, the pixel-space eigencrungi and the consistency scores.

- write the renders to `data/derived/eigen-clip/` instead, outside the corpus tree, and give `bucket_sync` an explicit second root so they still ship.
- alternatively give the three globs a shared exclusion helper. Either way a test must assert that a file placed in the derived tree does not appear in `embed_images`, `build_sprite` or `build_eigen`.

### Site

- `/eigen/` gets a mode toggle (**pixels** / **semantic**). Semantic mode keeps the slider list but the stage shows, for the current slider position, the nearest real archive images in CLIP space (top 6, computed in the browser from the shipped coefficients in the PCA subspace), and each retained component row shows its rendered filmstrip with the current position highlighted.
- one slider at a time drives the filmstrip; multiple sliders combine only in the nearest-real-images view. Say so in the copy.
- clicking a real image loads its coefficients and shows the original beside the nearest-neighbour panel.
- maths in `site/src/lib/eigen.ts` with vitest coverage.
- about page: PCA in CLIP space, extremes rendered by Kandinsky 2.2's decoder — itself one of the archive's models, so the renders are its guess at what lies along an axis, not ground truth.

### Verification

- pipeline checks green, including the contamination test above, a test that the bigG cache and the PCA agree on key order, and a test that the filmstrip index maths is monotone.
- site checks green; `agent-browser` smoke test that moving a slider changes the highlighted filmstrip frame and the nearest-images panel.
- `crungus sync`, push to `main`, confirm the live page loads the derived data from the bucket.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 every optimized image has a cached ViT-bigG-14 embedding in state/embeddings-bigg.npz, keyed like the existing cache, with the ViT-B/32 cache and its scores untouched
- [x] #2 crungus eigen --space clip writes 24 CLIP-space components with variance, sigma, per-component resampling stability and per-image coefficients in sigma units, plus the supervised crungus-ness axis
- [x] #3 Kandinsky filmstrips (mean, plus/minus 3 sigma and 7 steps between) are rendered only for components with stability above 0.7 and for the crungus-ness axis, keeping the median of three seeds by CLIP similarity
- [x] #4 the rendered AVIFs live outside data/optimized/ and a test asserts they are invisible to embed_images, build_sprite and build_eigen, while bucket_sync still ships them
- [x] #5 /eigen/ offers a semantic mode with the crungus-ness slider as headline, filmstrips for the retained components, the tail shown as unnamed with its stability, and the nearest real archive images for the current slider state
- [x] #6 clicking a real image loads its coefficients and shows the original beside the nearest-images panel, with pixels mode unchanged
- [x] #7 the about page explains the method and that the renders are Kandinsky's guess along an axis, not ground truth
- [x] #8 all pipeline and site checks are green, the agent-browser smoke test passes, and the live page loads the derived data from the bucket after sync and push
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Two measured deviations from the design, both forced by the decoder.

**Embeddings are cached unnormalised.** state/embeddings-bigg.npz holds raw
ViT-bigG-14 output (norm 41.3 +/- 1.4 across the archive), and the
decomposition runs at that scale, so mean + k*sigma*component is a point the
decoder can be handed directly. Anything wanting a cosine normalises on the
way in. The decoder turns out not to care: round-tripping eight archive images
retrieves the right original 8/8 at every scale from 41 down to 1.

**The guidance negative is not zeros.** The design said "empty negative
embedding", and a zero vector is not a point any picture maps to. Guiding four
times away from the prediction it produces drives every frame out of gamut:
the first full render came back magenta with the green channel at a third of
the other two, identically in float32 and float16. The fix is the negative
Kandinsky's own pipeline uses, its prior run on the empty prompt (cosine 0.29
to the archive mean, so it does not collide with the shared centre frame). It
restored the colour and lifted round-trip fidelity from 0.75 to 0.85, and the
margin over an unrelated archive image from +0.33 to +0.44.

Measurements. 19,344 images, 24 components, 54% of variance. Nineteen
reproduce above 0.7 -- the same count as the pixel basis, but a far cleaner
truncation: all nineteen sit above 0.893 and the other five below 0.454, where
the pixel scores are ragged (component 19 at 0.26, component 24 at 0.72). The
crungus-ness axis has cosine 0.319 +/- 0.058 with the archive. 121 frames
rendered (20 axes sharing one centre), mean CLIP cosine to target 0.796.

Timings on the RTX 6000: bigG embedding 20 min, decomposition 34 s, render 7
min.

Also fixed a latent bug in eigen.stability: a half of a small archive cannot
offer k components to compare against, which raised rather than scoring the
unreachable tail zero. Only reachable in tests at corpus scale, but wrong.

Separately, the build revealed a site-wide Astro whitespace bug (a prose line
running into an inline element on the next line loses the space between them)
in seventeen places, live since before this task. Fixed in b1c4304.
<!-- SECTION:NOTES:END -->
