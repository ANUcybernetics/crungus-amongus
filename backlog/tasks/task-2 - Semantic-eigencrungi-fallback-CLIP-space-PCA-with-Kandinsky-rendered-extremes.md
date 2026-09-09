---
id: TASK-2
title: 'Semantic eigencrungi fallback: CLIP-space PCA with Kandinsky-rendered extremes'
status: To Do
assignee: []
created_date: '2026-09-09 06:48'
labels:
  - pipeline
  - site
dependencies:
  - TASK-1
references:
  - 'https://huggingface.co/kandinsky-community/kandinsky-2-2-decoder'
  - pipeline/src/crungus_amongus/eigen.py
  - pipeline/src/crungus_amongus/analyzer.py
priority: medium
ordinal: 2000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Why

Fallback for task-1. If the StyleGAN2 trained on the archive fails its quality gate (collapsed, off-distribution, or Ben says no to the sample grid), we still want semantic eigencrungi that look good, just without real-time mixing in the browser. This version does the PCA in CLIP image-embedding space, where the components are things like photoreal-versus-cartoon and creature-versus-lettering rather than brightness and framing, and renders each component's extremes once with Kandinsky 2.2's decoder, which takes a CLIP image embedding directly. Only start this task if task-1's gate fails; it is not a second mode to ship alongside a working generator.

## Design

### Embeddings (`crungus eigen --space clip`)

- Kandinsky 2.2's decoder conditions on ViT-bigG-14 CLIP image embeddings (1280-d), not the ViT-B/32 (512-d) embeddings `analyzer.py` caches. Re-embed every optimized image with open-clip `ViT-bigG-14` / `laion2b_s39b_b160k` on the local GPU (a few minutes) into `state/embeddings-bigg.npz`, keyed like the existing cache. Keep the ViT-B/32 cache for consistency scores and the atlas; do not change them.
- PCA (reuse `eigen.pca`) on the 1280-d embeddings, 24 components, σ per component, same sign convention. Coefficients per image in σ units, as pixel mode already ships.

### Rendering the extremes

- for the mean embedding and each component at mean ± 3σ·v (49 embeddings), decode with `kandinsky-community/kandinsky-2-2-decoder` (diffusers, `image_embeds` input, 50 steps, 512 px, fixed seed, empty negative embedding). Run locally on the RTX 6000; rent a GPU only if diffusers will not install alongside the pipeline's torch, in which case run it as a standalone `uv run --script` with its own inline deps. Three seeds per embedding, keep the middle one by CLIP similarity to the target embedding so a single bad sample does not stand for a direction.
- also render 7 steps along each component (−3σ … +3σ) so the page can show a filmstrip per slider; 24 × 7 = 168 images plus the mean, encoded to AVIF at 256 px with the existing optimizer settings.
- write `data/optimized/eigen-clip/` with `eigen.json` (components: variance, sigma, name from a `[clip]` table in `data/eigen-names.toml`, real exemplar keys at each extreme, filmstrip keys; coefficients per image) and the AVIFs. `sync` ships it unchanged.

### Site

- `/eigen/` gets a mode toggle (**pixels** / **semantic**). Semantic mode keeps the same slider list but the stage shows, for the current slider position, the nearest real archive images in CLIP space (top 6 from the sprite, computed in the browser from the shipped coefficients, i.e. in the 24-d PCA subspace), and each component row shows its rendered filmstrip with the current position highlighted. One slider at a time drives the filmstrip; multiple sliders combine only in the nearest-real-images view. Say so in the copy.
- clicking a real image loads its coefficients (as pixel mode does) and shows the original beside the nearest-neighbour panel.
- maths (nearest neighbours in the PCA subspace, filmstrip index from a slider value) in `site/src/lib/eigen.ts` with vitest coverage.
- about page: replace the promised generator paragraph with what this is: PCA in CLIP space, extremes rendered by Kandinsky 2.2's decoder, which is one of the archive's own models, so the renders are its guess at what lies in that direction, not ground truth.

### Verification and deployment

- pipeline checks green, including a test that the bigG embedding cache and the PCA agree on key order and that the filmstrip index maths is monotone.
- site checks green; agent-browser smoke test that moving a slider changes the highlighted filmstrip frame and the nearest-images panel.
- `crungus sync`, push to `main`, confirm the live page loads `images.crungusamong.us/eigen-clip/eigen.json`.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 task-1's quality gate has failed and its notes record why; this task is not started otherwise
- [ ] #2 every optimized image has a cached ViT-bigG-14 CLIP embedding in state/embeddings-bigg.npz, keyed like the existing cache, with the ViT-B/32 cache and its scores untouched
- [ ] #3 crungus eigen --space clip writes data/optimized/eigen-clip/eigen.json with 24 CLIP-space components (variance, sigma, hand-names from the [clip] table of data/eigen-names.toml, real exemplars at each extreme, filmstrip keys) and per-image coefficients in sigma units
- [ ] #4 the mean embedding and 7 steps from minus to plus 3 sigma along every component are rendered with the Kandinsky 2.2 decoder, the median-by-CLIP-similarity of three seeds kept, encoded as AVIF and shipped by crungus sync
- [ ] #5 /eigen/ offers a semantic mode showing each component's rendered filmstrip with the current slider position highlighted and the nearest real archive images to the current slider state, with pixels mode unchanged
- [ ] #6 clicking a real image loads its coefficients and shows the original beside the nearest-images panel
- [ ] #7 the about page describes the method and that the renders are Kandinsky's guess, not ground truth
- [ ] #8 all pipeline and site checks are green, the browser smoke test passes, and the live page loads the eigen-clip data from the bucket after sync and push
<!-- AC:END -->
