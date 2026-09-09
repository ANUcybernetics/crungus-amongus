---
id: TASK-1
title: >-
  Generator eigencrungi: StyleGAN2 trained on the archive with GANSpace sliders
  in the browser
status: To Do
assignee: []
created_date: '2026-09-09 06:48'
labels:
  - pipeline
  - site
  - gan
dependencies: []
references:
  - 'https://arxiv.org/abs/2004.02546'
  - 'https://arxiv.org/abs/2502.01639'
  - 'https://arxiv.org/abs/2006.10738'
  - pipeline/src/crungus_amongus/eigen.py
  - site/src/pages/eigen.astro
priority: high
ordinal: 1000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Why

The pixel-space eigencrungi (`crungus eigen`, `/eigen/`) are the faithful Turk and Pentland homage, but with no alignment the components are mostly light, framing and palette, and every reconstruction is a blur. The literature moved the same trick into a generator's latent space (GANSpace 2020; Concept Sliders 2024; SliderSpace 2025), where each slider re-renders a sharp image. We want that version: train a small generator on the archive itself, take the principal directions of its latent space, and put them on sliders that render in the browser in real time. Conceptually it is the eigencrungi of a model that has learned all 91 models' crungi --- a second-order cryptid. Cost of compute is not a constraint (Ben, 2026-09-09); quality is. The task carries an explicit go/no-go gate; if the gate fails, the fallback is the CLIP-space version with Kandinsky-rendered extremes (task-2).

## Shape of the result

- new pipeline stages `crungus gan train`, `crungus gan directions`, `crungus gan export`, writing under `state/gan/` (checkpoints, gitignored) and `data/optimized/gan/` (what the site fetches)
- `/eigen/` gains a **generator** mode alongside the existing **pixels** mode; the generator mode is the default when the browser can run it and shows download progress while the model arrives
- sliders edit a base latent (the mean, a random sample, or an inverted archive image) along PCA directions in W space, GANSpace-style, with the rendered ±3σ extremes of each component beside it and a hand-name from `data/eigen-names.toml`

## Design

### Training (`crungus gan train`)

- data: every `data/optimized/**/*.avif`, centre-cropped with `sprite.square` to 128 px RGB, plus horizontal flips. Cache once as `state/gan/dataset.npy` (uint8, ~80 MB) so epochs don't decode AVIF.
- model: StyleGAN2 at 128 px. Prefer a compact in-repo implementation in `pipeline/src/crungus_amongus/gan.py` (mapping MLP 8×512, modulated/demodulated convs, skip-connection generator, residual discriminator, R1 penalty lazy every 16 steps with γ=1, EMA generator β=0.999, Adam lr 0.002 β=(0, 0.99)) with plain ops so ONNX export is straightforward. `lucidrains/stylegan2-pytorch` is acceptable instead only if it installs and trains cleanly on the pipeline's torch 2.13 / Python 3.14 without pins. No custom CUDA ops (NVlabs code is out).
- small-data regime: DiffAugment (colour, translation, cutout) on everything the discriminator sees, p=1.0. Channel cap 256, batch 32.
- schedule: 5000 kimg default, checkpoint plus an 8×8 EMA sample grid every 100 kimg to `state/gan/`, resumable from the latest checkpoint (`--resume`). Budget ≤ 8 GPU-hours on the local RTX 6000 Ada before the gate decides. A bigger rented GPU only speeds this up; use one if the local box is busy.
- seed fixed; log loss, R1 and kimg/s with loguru.

### Quality gate (the go/no-go test)

Run at 1000 kimg and at the end. All three must hold at the end for the task to continue past training:

1. **Not collapsed:** CLIP consistency (existing `consistency_scores`) over 1000 EMA samples < 0.90, i.e. the samples are at least as varied as the archive's most consistent model.
2. **On distribution:** mean cosine similarity between each of 1000 EMA samples and its nearest archive image in CLIP space ≥ 0.80, and no archive image is the nearest neighbour of more than 5% of samples (no memorisation of a few images).
3. **Looks like crungi:** Ben inspects the final 8×8 EMA grid and the ±3σ direction renders and says go. Post the grid in the task notes.

Two hyperparameter attempts are allowed inside the budget (e.g. capacity 128 → 256, DiffAugment p 1.0 → 0.6, kimg 5000 → 8000). If the gate still fails: record the grids and metrics in the notes, mark this task's AC 3 as failed, and start task-2 instead of continuing.

### Directions (`crungus gan directions`)

- sample 20 000 z → w through the EMA mapping network, no truncation. PCA on the 512-d w vectors (reuse `eigen.pca`), keep 24 components; σ per component; sign fixed so the largest-|coefficient| sample is positive (same convention as `eigen.py`).
- render the mean-w image and, per component, the image at mean ± 3σ·v (the GANSpace figure), into `data/optimized/gan/extremes.webp` (lossless, tiles of 128 px: mean, then −/+ per component) --- these are the exemplars beside each slider, replacing the real-image exemplars of pixel mode.
- inversion: for one image per model (the cover image, 91 images), optimise w in W space (not W+) for 500 steps against LPIPS(VGG) + L2 from the mean w, seeded by the closest of the 20 000 samples in CLIP space. Store as `inverted: {key: w[512]}`. Extend to every archive image later only if the per-model set looks convincing.
- write `data/optimized/gan/gan.json`: `{ mean_w, components: [{ variance, sigma, name, vector[512] }], inverted, synthesis: "<hashed .onnx key>", mapping: "<hashed .onnx key>", resolution }`. Names come from a `[generator]` table in `data/eigen-names.toml` (the existing `[names]` table stays for pixel mode; document both in the file header).

### Export (`crungus gan export`)

- export the EMA synthesis network (w[1,512] → RGB uint8 [128,128,3]) and the mapping network (z[1,512] → w[1,512]) to ONNX opset 17, fp16 weights, dynamic batch off. Filenames carry a content hash (`synthesis-<sha256[:12]>.onnx`) so the bucket's immutable cache is correct; `gan.json` (mutable, 5-min cache) points at the current ones.
- parity test: torch vs onnxruntime output on 8 fixed w's, max abs pixel error ≤ 3/255. Add `onnxruntime` to the dev group for this test only.
- size target ≤ 40 MB for synthesis; report the actual size in the notes. If over, reduce channel cap before reducing resolution.
- `bucket_sync`: add `.onnx` → `application/octet-stream` (immutable cache, since the name is hashed). Add `state/gan/` to `.gitignore`. Weights never enter git.

### Site

- add `onnxruntime-web` to `site/`; copy its WASM assets into `site/public/ort/` at build (a small script in `package.json`, like `sync-images`) and point `ort.env.wasm.wasmPaths` there. GitHub Pages cannot set COOP/COEP, so threads are unavailable: use the WebGPU execution provider when `navigator.gpu` exists, else single-threaded WASM. Say which one is active in the stage caption.
- `/eigen/` gets a mode toggle (**pixels** / **generator**), same visual pattern as the archive's sort toggle. Generator mode is the default when the page can run it; pixels mode is the instant no-download fallback and stays as it is.
- state in generator mode is a full 512-d w: `w = base + Σ offsets`. Slider k shows `⟨w − mean, v_k⟩ / σ_k`; moving it adds `(new − old)·σ_k·v_k`. Base is the mean w on load, a fresh mapping-network sample on "a real crungus" (rename the button in this mode to "a new crungus"), or an inverted w when an archive image is chosen from a per-model picker (show the original beside the render, as pixel mode does). Reset returns to the mean.
- rendering: run synthesis on `input`, coalesced with requestAnimationFrame and dropped while a run is in flight; draw the 128 px output to the same stage canvas. Target < 100 ms per frame on WebGPU on a laptop; WASM will be around a second, which is acceptable with the frame-dropping.
- each component row: the rendered −3σ tile, the slider, the +3σ tile, the name or number, variance share. Keep the maths in `site/src/lib/eigen.ts` (or a sibling `generator.ts`) with vitest coverage for the slider ↔ w arithmetic.
- copy: extend the intro and the about page's eigencrungi section with two sentences on what the generator is (StyleGAN2 trained on the archive; the sliders are principal directions of its latent space; it is not any of the 91 models). Colophon gains "a StyleGAN2 trained on the archive · run in the browser with onnxruntime-web".
- README: the three new stages and the model asset flow. CLAUDE.md: one constraint line --- generator weights and checkpoints never go in git; the bucket copies are content-hashed and immutable, so a retrained model means new keys plus a `gan.json` update.

### Verification and deployment

- pipeline: `uv run ruff check . && uv run ruff format --check . && uvx ty check && uv run pytest` green, including the parity test and unit tests for DiffAugment shapes, W-space PCA, and the inversion loss.
- site: `pnpm run typecheck && pnpm run lint && pnpm run lint:css && pnpm run format:check && pnpm run test && pnpm run build` green.
- browser smoke test with `agent-browser`: open `/eigen/`, wait for the generator, move two sliders, confirm the stage canvas changes (compare pixel data before/after) on both execution providers (force WASM by stubbing `navigator.gpu`).
- `crungus sync` then push to `main`; confirm `https://crungusamong.us/eigen/` loads the generator from `images.crungusamong.us/gan/` with correct content-type and cache headers.
- commit at each checkpoint (training code, directions, export, site) --- only on a green state.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 crungus gan train trains a StyleGAN2 at 128 px on the archive images on this machine, resumable, writing checkpoints and EMA sample grids under state/gan/ (gitignored)
- [ ] #2 the quality gate passes: 1000 EMA samples have CLIP consistency below 0.90, mean nearest-archive-image CLIP similarity of at least 0.80 with no archive image nearest to more than 5% of samples, and Ben approves the final sample grid posted in the task notes
- [ ] #3 if the gate fails after two attempts within 8 GPU-hours, the metrics and grids are recorded in the notes and task-2 (Kandinsky fallback) is started instead
- [ ] #4 crungus gan directions writes data/optimized/gan/gan.json (mean w, 24 W-space PCA components with sigma and hand-names from the [generator] table of data/eigen-names.toml, inverted w for one image per model) and extremes.webp with the mean and the rendered plus/minus 3 sigma tile of every component
- [ ] #5 crungus gan export writes content-hashed fp16 ONNX files for the synthesis and mapping networks, synthesis at most 40 MB, and a test shows onnxruntime output matches torch within 3/255 per pixel
- [ ] #6 crungus sync uploads .onnx files with immutable cache-control and application/octet-stream content type, and the weights never enter git
- [ ] #7 /eigen/ offers a generator mode, default when the browser can run it, that downloads the model with visible progress and renders a crungus on the stage from the sliders, on WebGPU where available and single-threaded WASM otherwise, stating which is active
- [ ] #8 in generator mode sliders edit the current latent along PCA directions (slider value equals the latent's coefficient on that component), a new random crungus can be sampled in the browser via the mapping network, reset returns to the mean crungus, and moving sliders on WebGPU takes under 100 ms per frame on a laptop
- [ ] #9 each component row shows its rendered minus and plus 3 sigma tiles, its variance share and its hand-name or number, and at least one archive image per model can be loaded as its inverted latent with the original shown beside the render
- [ ] #10 pixels mode remains available as the instant no-download fallback with no regression
- [ ] #11 the browser smoke test (agent-browser) confirms the stage canvas changes when a slider moves, on both execution providers
- [ ] #12 all pipeline and site checks are green; README, CLAUDE.md and the about page describe the generator, its stages and the weights-never-in-git constraint
- [ ] #13 the change is synced to the bucket and pushed to main, and https://crungusamong.us/eigen/ loads the generator from images.crungusamong.us/gan/ with the expected content-type and cache headers
<!-- AC:END -->
