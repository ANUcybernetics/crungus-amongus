---
id: TASK-4
title: Regenerate the image corpus at 100 outputs per prompt
status: To Do
assignee: []
created_date: '2026-09-09 07:44'
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
- [ ] #1 every one of the 83 image models is confirmed to still resolve at its pinned version before any generation runs, with the result recorded in the task notes
- [ ] #2 OUTPUTS_PER_PROMPT is per-modality: 100 for image, 10 for audio, with the prompt sets themselves unchanged
- [ ] #3 crungus generate was dry-run first and the estimate reported, and no model version pin was bumped
- [ ] #4 every (image model, prompt) pair has exactly 100 optimized images, with no pair left short and manifest.jsonl only appended to
- [ ] #5 optimize, analyze, sprite, eigen, sync and publish have all been re-run over the larger corpus and the site builds from it
- [ ] #6 the recomputed consistency jackknife SE and top-24 subspace overlap are reported in the notes
- [ ] #7 all pipeline and site checks are green
<!-- AC:END -->
