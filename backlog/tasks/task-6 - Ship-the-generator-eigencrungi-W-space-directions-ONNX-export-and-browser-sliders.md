---
id: TASK-6
title: >-
  Ship the generator eigencrungi: W-space directions, ONNX export and browser
  sliders
status: To Do
assignee: []
created_date: '2026-09-09 07:46'
labels:
  - pipeline
  - site
  - gan
dependencies:
  - TASK-1
references:
  - 'https://arxiv.org/abs/2004.02546'
  - site/src/pages/eigen.astro
  - pipeline/src/crungus_amongus/bucket_sync.py
priority: medium
ordinal: 1000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Why

Task-1 trains a generator and stops at a go/no-go gate. This task takes a generator that passed and turns it into sliders on `/eigen/`: principal directions of its W space, GANSpace-style, rendering in the browser in real time. Start only if task-1's gate passed.

## Design

### Directions (`crungus gan directions`)

- sample 20 000 z to w through the EMA mapping network, no truncation. PCA on the 512-d w vectors (reuse `eigen.pca`), keep 24 components, sigma per component, sign fixed as in `eigen.py`.
- **compute the same per-component resampling stability score used elsewhere in the project, and expect the same degeneracy.** In CLIP space only 2 of 24 components reproduce above 0.9, because the eigenvalue gaps past the first are tiny; StyleGAN2's W is if anything worse for tied eigenvalues. Name only components above 0.7 stability and render the rest as numbers. Do not commission a 24-entry name table.
- render the mean-w image and each retained component at mean +/- 3 sigma into an extremes sheet — these are the exemplars beside each slider.
- **skip optimised inversion.** Inverting an out-of-distribution archive image (vector art, lettering artefacts) into a small GAN's W, rather than W+, produces a generic sample, and showing the original beside it foregrounds the failure. Instead take the nearest of the 20 000 sampled w vectors by CLIP similarity and label it honestly as "the closest crungus the generator knows". This also drops an undeclared LPIPS/VGG dependency.
- write `gan.json`: mean w, components (variance, sigma, stability, name, vector), the nearest-sample w per model, hashed ONNX keys, resolution, **and the training checkpoint's hash** — component identity is tied to one training run, so a retrain invalidates the names and the site must fall back to numbers on a mismatch.

### Export (`crungus gan export`)

- export the EMA synthesis network (w[1,512] to RGB uint8 [128,128,3]) and the mapping network (z[1,512] to w[1,512]) to ONNX opset 17, dynamic batch off. Filenames carry a content hash so the bucket's immutable cache is correct; `gan.json` (mutable, 5-min cache) points at the current pair.
- **resolve precision before treating the size target as settled.** onnxruntime-web's WebGPU EP handles fp16; its WASM EP has thin fp16 kernel coverage, so one fp16 file for both paths will likely fail on the fallback. An fp32 build of a ~10M-parameter model is about 40 MB, right at the cap. Decide early between two builds or an fp16 model with casts, and report the actual sizes.
- parity test: torch versus onnxruntime output on 8 fixed w vectors, max abs pixel error at most 3/255. Add `onnxruntime` to the dev group for this test.
- `bucket_sync` gains `.onnx` mapped to `application/octet-stream`, immutable-cached since the name is hashed.

### Site

- add `onnxruntime-web`; copy its WASM assets into `site/public/ort/` at build (a small script like `sync-images`) and point `ort.env.wasm.wasmPaths` there. GitHub Pages cannot set COOP/COEP, so SharedArrayBuffer and threads are unavailable: use the WebGPU execution provider when `navigator.gpu` exists, else single-threaded WASM. State which is active in the stage caption.
- `/eigen/` gains a **generator** mode alongside pixels and semantic. Measured budget: synthesis is about 10.4 GFLOP per image, so WebGPU under 100 ms on a laptop is achievable and single-threaded WASM lands around a second. **Default to generator mode only when WebGPU is present**; on the WASM path make it opt-in behind a click, since it means a multi-megabyte download and second-scale frames. Show download progress.
- state is a full 512-d w: `w = base + sum of offsets`. Slider k shows the coefficient on component k in sigma units; moving it adds the difference along that component. Base is the mean w, a fresh mapping-network sample, or a model's nearest-sample w. Reset returns to the mean.
- rendering coalesced with requestAnimationFrame, dropping frames while a run is in flight; draw to the same stage canvas.
- keep the maths in `site/src/lib/` with vitest coverage for the slider-to-w arithmetic.
- copy: extend the intro and about page with what the generator is, and that it is not any of the archive's models. Colophon gains a line about onnxruntime-web.
- README: the new stages and the model asset flow. CLAUDE.md: one line that generator weights never go in git and that a retrain means new hashed keys plus a `gan.json` update.

### Verification

- pipeline and site checks green, including the parity test and the W-space PCA tests.
- `agent-browser` smoke test: open `/eigen/`, wait for the generator, move two sliders, confirm the stage canvas pixel data changes, on both execution providers (force WASM by stubbing `navigator.gpu`).
- `crungus sync` then push; confirm the live page loads the model from the bucket with the expected content-type and cache headers.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 crungus gan directions writes gan.json with the mean w, 24 W-space PCA components carrying variance, sigma and resampling stability, the training checkpoint hash, and a nearest-sample w per model
- [ ] #2 only components with stability above 0.7 are given hand-names; the rest render as numbers, and the site falls back to numbers when the checkpoint hash does not match
- [ ] #3 an extremes sheet shows the mean and the rendered plus/minus 3 sigma tiles for every retained component
- [ ] #4 crungus gan export writes content-hashed ONNX for the synthesis and mapping networks with the precision question resolved for both execution providers and actual sizes reported, and a test shows onnxruntime matches torch within 3/255 per pixel
- [ ] #5 crungus sync uploads .onnx with immutable cache-control and application/octet-stream, and weights never enter git
- [ ] #6 /eigen/ offers a generator mode that renders from the sliders, defaulting on only when WebGPU is present and opt-in behind a click on the WASM path, showing download progress and stating which provider is active
- [ ] #7 sliders edit the latent along PCA directions in sigma units, a new random crungus can be sampled via the mapping network, reset returns to the mean, and WebGPU frames take under 100 ms on a laptop
- [ ] #8 pixels and semantic modes remain available with no regression
- [ ] #9 the agent-browser smoke test confirms the stage canvas changes when a slider moves, on both execution providers
- [ ] #10 README, CLAUDE.md and the about page describe the generator, its stages and the weights-never-in-git constraint
- [ ] #11 all pipeline and site checks are green, and the live page loads the generator from the bucket with the expected headers after sync and push
<!-- AC:END -->
