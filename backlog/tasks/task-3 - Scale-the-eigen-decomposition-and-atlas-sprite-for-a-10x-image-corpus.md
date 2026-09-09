---
id: TASK-3
title: Scale the eigen decomposition and atlas sprite for a 10x image corpus
status: Done
assignee: []
created_date: '2026-09-09 07:44'
updated_date: '2026-09-09 10:13'
labels:
  - pipeline
  - site
dependencies: []
references:
  - pipeline/src/crungus_amongus/eigen.py
  - pipeline/src/crungus_amongus/sprite.py
  - site/src/pages/atlas.astro
priority: high
ordinal: 500
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Why

Every published number about the archive rests on `state/embeddings.npz`, and the eigencrungi rest on `eigen.py`'s Turk-Pentland Gram trick and the atlas on a single sprite sheet. Both were sized for ~1600 images. Raising the sample count to 100 per prompt (task-4) takes the corpus to ~16 000 images, at which point the sprite becomes an 8128x8064 WebP (262 MB decoded, versus 26 MB today) that no phone will open, and `load_pixels` plus its centred copy plus a 16k x 16k float64 Gram matrix peaks around 9 GB. The Gram trick is the right algorithm precisely because N is much smaller than D; at N=16 000 it stops being so.

This is the prerequisite for the corpus regeneration: land it first so the pipeline can digest the bigger archive.

## Design

### Eigen decomposition

- replace the explicit Gram-matrix eigendecomposition in `eigen.pca` with a randomised SVD over the centred matrix, keeping the same `Pca` dataclass, the same sign convention (largest-|coefficient| sample projects positive) and the same variance-ratio semantics. Peak memory must stay under ~4 GB at N=16 000, SIDE=128.
- keep the existing pure-function shape: `pca(rows, k)` in, `Pca` out. The callers do not change.
- a test pins the new implementation against the current one on a small random matrix: components agree up to sign to within 1e-4, variance ratios to within 1e-6.

### Atlas sprite

- `sprite.build_sprite` emits tiles rather than one sheet: `sprite-000.webp`, `sprite-001.webp`, ..., each at most 4096x4096 px, with `sprite.json` gaining a `tiles` array and each key resolving to (tile index, x, y). Cell size stays 64 px.
- the site's atlas page loads tiles lazily as the viewport needs them rather than all at once.
- `sprite.json` stays a mutable-cached JSON; the tiles are content-addressed the way the rest of the optimized tree is.

### Verification

- pipeline checks green (`uv run ruff check . && uv run ruff format --check . && uvx ty check && uv run pytest`), including the PCA equivalence test and a sprite test that a synthetic 20 000-key corpus tiles correctly and every key resolves to exactly one tile.
- site checks green; `agent-browser` smoke test on `/atlas/` confirms pan and zoom still render cells at the current corpus size (no visual regression).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 eigen.pca uses a randomised SVD and peaks under 4 GB at N=16000, SIDE=128, with a test pinning it against the current Gram implementation to within 1e-4 on components and 1e-6 on variance ratios
- [x] #2 build_sprite emits tiles of at most 4096x4096 px with sprite.json carrying a tiles array, and a test shows a synthetic 20000-key corpus resolves every key to exactly one tile
- [x] #3 the atlas page loads sprite tiles lazily and pan/zoom shows no regression at the current corpus size under an agent-browser smoke test
- [x] #4 all pipeline and site checks are green
<!-- AC:END -->
