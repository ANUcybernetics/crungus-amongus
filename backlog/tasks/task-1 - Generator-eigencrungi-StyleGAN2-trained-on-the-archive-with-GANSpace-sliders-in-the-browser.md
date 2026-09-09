---
id: TASK-1
title: Train a StyleGAN2 on the archive and evaluate the eigencrungi quality gate
status: To Do
assignee: []
created_date: '2026-09-09 06:48'
updated_date: '2026-09-09 07:46'
labels:
  - pipeline
  - gan
dependencies:
  - TASK-4
references:
  - 'https://arxiv.org/abs/2004.02546'
  - 'https://arxiv.org/abs/2502.01639'
  - 'https://arxiv.org/abs/2006.10738'
  - pipeline/src/crungus_amongus/eigen.py
  - pipeline/src/crungus_amongus/analyzer.py
priority: medium
ordinal: 900
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Why

The pixel-space eigencrungi are the faithful Turk and Pentland homage, but with no alignment the components are mostly light, framing and palette — component 1 correlates with mean image brightness at r = 0.996 — and every reconstruction is a blur. The literature moved the same trick into a generator's latent space (GANSpace 2020; Concept Sliders 2024; SliderSpace 2025), where each slider re-renders a sharp image. This task trains a small generator on the archive itself so that later work can take the principal directions of its latent space. Conceptually it is the eigencrungi of a model that has learned the archive's crungi — a second-order cryptid.

This task ends at a go/no-go gate. Shipping the sliders is task-6, and starts only if the gate passes.

## Design

### Data

Every image under `data/optimized/`, centre-cropped with `sprite.square` to 128 px RGB, plus horizontal flips. Cache once as `state/gan/dataset.npy` (uint8) so epochs do not decode AVIF.

This task should run **after** the corpus reaches 100 images per prompt (task-4). The reason is the binding one: the archive has 83 image models x 2 prompts = 166 style modes, so at the current size a generator sees about 10 examples per mode, which is memorisation territory rather than distribution learning. At 100 per prompt it is ~16 000 images and ~100 per mode — roughly AFHQ scale, and the regime where the small-data GAN literature actually holds. Training on the 1594-image archive is not worth the attempt.

Consider a class-conditional generator over the 83 model labels with a projection discriminator. It costs almost nothing at this size, gives the model a way to represent the archive's multimodality instead of averaging over it, and makes "a model that learned all of them" literally true.

### Model

StyleGAN2 at 128 px. Get **one known-good reference implementation training first**, even if it is replaced later: a from-scratch generator confounds an implementation bug with a genuine negative result, and "the gate failed" then means nothing. Note that NVlabs `stylegan2-ada-pytorch` ships pure-PyTorch `_ref` fallbacks for `bias_act` and `upfirdn2d` and does not require compiling CUDA ops — the real blockers there are its non-commercial licence and Python 3.14 compatibility, not custom ops. Whatever is chosen must export cleanly to ONNX later.

Settings: mapping MLP 8x512, modulated/demodulated convs, skip-connection generator, residual discriminator, R1 lazily every 16 steps with gamma=1, EMA generator beta=0.999, Adam lr 0.002 betas=(0.0, 0.99), channel cap 256, batch 32. Path length regularisation off (standard for small data). Seed fixed; log loss, R1 and kimg/s with loguru.

Small-data augmentation: prefer **ADA** (adaptive augmentation probability) over fixed DiffAugment. DiffAugment applies its policies deterministically and has no p to tune; the adaptive probability is ADA's, and for a heterogeneous archive letting p adapt is the better default.

### Budget

Measured on this machine: a pure-PyTorch StyleGAN2-shaped step at 128 px, batch 32, lazy R1 runs at 0.097 s/step, or about 1190 kimg/hr. That is an optimistic floor (no augmentation, no EMA copy, fp32), so assume 800-900 kimg/hr in practice.

So compute is not the constraint and there is no 8-hour cap. Default to **20 000 kimg**, about a day, and checkpoint plus an 8x8 EMA sample grid every 500 kimg to `state/gan/`, resumable with `--resume`. The small-data StyleGAN2-ADA results train in this range; 5000 kimg is too few. Evaluate the gate at each checkpoint so a hopeless run can be stopped early.

### The quality gate

All three must hold at the end.

1. **Not collapsed.** CLIP consistency (mean pairwise cosine similarity, as `analyzer.py` computes it) over 1000 EMA samples must fall within **0.585 +/- 0.05** — the archive's own global mean pairwise similarity. This is the right reference class: 1000 samples are meant to span the whole archive, so comparing them to a within-model set of ten near-duplicates is a category error. It is two-sided: a sample set markedly more varied than the archive is noise, not diversity.
2. **On distribution, without memorising.** Mean cosine similarity between each of 1000 EMA samples and its nearest archive image in CLIP space must be at least **0.80** (the archive's own cross-model nearest-neighbour similarity is mean 0.849, p10 0.757, so this asks a sample to sit between the tenth percentile and the mean of real images), **and** no archive image may be the nearest neighbour of more than **1%** of samples. The archive's own maximum concentration is 0.50%, so 1% is already generous.
3. **Looks like crungi.** Ben inspects the final 8x8 EMA grid and says go. Post the grid in the task notes.

Two hyperparameter attempts are allowed. If the gate still fails, record the grids and metrics in the notes and stop — task-2 is already the primary semantic eigencrungi and does not depend on this.

### Housekeeping

- add `state/gan/` to `.gitignore`. Weights and checkpoints never enter git.
- unit tests for the augmentation pipeline's output shapes and for the dataset cache round-tripping.
- pipeline checks green: `uv run ruff check . && uv run ruff format --check . && uvx ty check && uv run pytest`.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 crungus gan train trains a StyleGAN2 at 128 px on the archive, resumable, writing checkpoints and 8x8 EMA sample grids every 500 kimg under state/gan/ (gitignored)
- [ ] #2 training starts from a known-good reference implementation that is verified to train before any bespoke rewrite, so a failed gate cannot be an implementation bug
- [ ] #3 1000 EMA samples have CLIP consistency within 0.585 +/- 0.05, matching the archive's own global mean pairwise similarity
- [ ] #4 1000 EMA samples have mean nearest-archive-image CLIP similarity of at least 0.80, with no archive image nearest to more than 1% of samples
- [ ] #5 Ben approves the final EMA sample grid, posted in the task notes
- [ ] #6 if the gate fails after two hyperparameter attempts, the grids and metrics are recorded in the notes and the task is closed as failed
- [ ] #7 weights and checkpoints never enter git, and all pipeline checks are green
<!-- AC:END -->
