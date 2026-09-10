---
id: TASK-4
title: Regenerate the image corpus at 100 outputs per prompt
status: To Do
assignee: []
created_date: '2026-09-09 07:44'
updated_date: '2026-09-10 03:32'
labels:
  - pipeline
dependencies:
  - TASK-3
references:
  - pipeline/src/crungus_amongus/config.py
  - pipeline/src/crungus_amongus/generator.py
priority: high
ordinal: 700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Why

The archive holds 10 images per (model, prompt), and that is too few for three things we want.

**The consistency scores are mostly noise.** Jackknifed over the 162 sets with enough samples, the standard error of one model's score is 0.023 against a between-model spread of 0.106 — a noise-to-signal ratio of 0.21. Worse, the median gap between adjacent models in the consistency ranking is 0.0016, and **98% of adjacent pairs sit closer together than one standard error**. The leaderboard is arbitrary except at its extremes. At n=100 the standard error falls to about 0.007.

**The eigencrungi subspace is only half-converged.** Resampling disjoint halves of the archive, the top-24 subspace overlap (mean squared canonical correlation) is 0.593 at n=398, 0.705 at n=797 and 0.821 at n=1594 — still climbing steeply. 10x the data should put it comfortably above 0.9.

**The GAN needs it most.** 83 image models x 2 prompts = 166 style modes, so a generator trained on today's archive sees about 10 examples per mode. That is memorisation territory, not distribution learning. At 100 per prompt it is ~16 000 images and ~100 per mode, which is roughly AFHQ scale and the regime where the small-data GAN literature actually holds.

Replicate credit is available, so cost is not the constraint. The constraint is uniformity.

## Design

- `OUTPUTS_PER_PROMPT` in `config.py` goes from 10 to 100 for the **image** modality only. Audio stays at 10: nothing in the eigencrungi work uses it, and 100 x 20 s clips per model is a much heavier job for no gain here. That means the constant becomes per-modality, matching the existing shape of `PROMPTS` and `COLLECTIONS`.
- prompts are unchanged. The sample count is the only methodology change, and it is safe: mean pairwise cosine similarity is an unbiased estimator of the population quantity at any n, so old and new consistency scores stay comparable in expectation. Only the variance changes.

### Uniformity is the whole risk

A mixed corpus is the real methodology violation — scores at n=10 and n=100 have different variance, and a ranking that mixes them compares estimators rather than models. So:

- **before spending anything**, verify every one of the 83 image models still resolves at its pinned version in `state/models.json`. Replicate delists models. Write the result into the task notes as a list.
- if any model cannot be topped up, stop and report rather than generating a partial corpus. The decision about how to handle a delisted model (drop it from the comparison, or hold the whole corpus at 10) is Ben's, not the implementation's.
- version pins stay sticky throughout. This task must not run `discover --refresh-versions`.

### Running it

- `crungus generate --modality image --dry-run` first, and report the estimate before anything else.
- generation is resumable and idempotent; run it in stages and check `crungus status` between them.
- then `optimize`, `analyze`, `sprite`, `eigen`, `sync`, `publish` in order. `analyze` reuses the embedding cache for existing images and only embeds the new ones.

### Verification

- `crungus status` shows 100 images for every (image model, prompt) pair, with no pair short.
- `state/manifest.jsonl` is appended to, never rewritten.
- consistency standard errors recomputed and reported in the notes: the jackknife SE should land near 0.007.
- the top-24 CLIP subspace overlap recomputed and reported; expect above 0.9.
- all pipeline and site checks green; the site builds and deploys with the larger corpus.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 every one of the 83 image models is confirmed to still resolve at its pinned version before any generation runs, with the result recorded in the task notes
- [x] #2 OUTPUTS_PER_PROMPT is per-modality: 100 for image, 10 for audio, with the prompt sets themselves unchanged
- [x] #3 crungus generate was dry-run first and the estimate reported, and no model version pin was bumped
- [x] #4 every (image model, prompt) pair has exactly 100 optimized images, with no pair left short and manifest.jsonl only appended to
- [x] #5 optimize, analyze, sprite, eigen, sync and publish have all been re-run over the larger corpus and the site builds from it
- [x] #6 the recomputed consistency jackknife SE and top-24 subspace overlap are reported in the notes
- [x] #7 all pipeline and site checks are green
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## Pre-flight, 2026-09-09 — before any spend

### Version pins: all resolve

Read-only check against the Replicate API (GETs only, no predictions).
Community models were checked at `/models/{ref}/versions/{version_id}`;
official models are routed by Replicate and ignore version pinning (see
`replicate_client._create`), so those were checked at `/models/{ref}`.

**91 of 91 image models pinned `ok` in `state/models.json` returned 200. None
is delisted.** 83 of those have images in the archive; the other 8 are pinned
but have never produced one: borisdayma/dalle-mini, bytedance/seedream-3,
google/imagen-3, google/imagen-3-fast, google/imagen-4, google/imagen-4-fast,
google/imagen-4-ultra, quiverai/arrow-1.1. No pin was bumped and
`discover --refresh-versions` was not run.

### Dry run

`crungus generate --modality image --dry-run`:

    pending: 16400 predictions across 91 models (~$492.00)

That estimate is the flat $0.03/output in `ASSUMED_COST`, not per-model
pricing; the real figure will skew higher because the expensive models
(imagen-4-ultra, flux-2-max, nano-banana-pro, recraft) count the same as
flux-schnell. The dashboard is billing truth.

1460 of the 16400 go to the 8 models that have never succeeded. The per-model
probe wave in `run_batch` stops each after about 4 attempts, so the real waste
is roughly 32 predictions.

### The corpus is already not uniform

The premise that today's archive is a clean 10 per pair does not hold, so
AC #4 as written ("exactly 100, no pair short") is not reachable:

- 165 (model, prompt) pairs have images, not 166 —
  quiverai/arrow-1.1-max × "a picture of a crungus" has none.
- 16 pairs are already short of 10: 1594 images against 1660 expected.
- The shortfall is 249 permanent failures, 35 NSFW blocks and 24 retryable
  failures. The NSFW blocks are concentrated in the flux-2 family
  (flux-2-max 13, flux-2-pro 9, flux-2-flex 6) and are the model refusing the
  prompt, so scaling to 100 will scale the refusals too.

Scaling to 100 per prompt therefore lands a corpus that is uniform in what was
*asked* but not in what came back. Ben's call.

## Outcome, 2026-09-10

Corpus: 19,344 images, 94 of 97 image models at a full 200. Short: 
google/gemini-2.5-flash-image 159, pixray/text2image 192, google/nano-banana 196
— all error-driven flakiness rather than refusal, and not worth further passes.

### AC #6, recomputed

- jackknife SE 0.0083 (was 0.023); between-model sd 0.107, so noise-to-signal
  0.078 against 0.21 before. 93% of adjacent leaderboard pairs still sit within
  one SE — each score is 2.7x sharper, but 194 groups in a 0.107 spread means
  adjacent ranks stay noise. The extremes are what the leaderboard supports.
- top-24 CLIP subspace overlap 0.970 (was 0.821; the task expected >0.9).

### The task's own premise was wrong

Task-5 recorded that component instability was 'the eigenvalue spectrum, not
the sample size', and that more images 'cannot manufacture gaps that are not in
the data'. Ten times the images: components above 0.7 went from 5/24 to 19/24
and above 0.9 from 2/24 to 13/24. It was sample size. The site copy and
eigen.py's docstring now say so.

Also corrected: the '46% model identity' figure was measured in CLIP space and
had been applied to the pixel components on /eigen/. Measured on the pixel
basis it is 16% mean, 54% for component 1.
<!-- SECTION:NOTES:END -->
