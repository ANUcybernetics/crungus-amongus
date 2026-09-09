---
id: TASK-5
title: >-
  Rework the eigencrungi axes: truncate to what reproduces, add a supervised
  crungus-ness slider
status: To Do
assignee: []
created_date: '2026-09-09 07:45'
labels:
  - pipeline
  - site
dependencies: []
references:
  - pipeline/src/crungus_amongus/eigen.py
  - site/src/pages/eigen.astro
  - site/src/lib/eigen.ts
  - data/eigen-names.toml
priority: high
ordinal: 600
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Why

`/eigen/` ships 24 named components. Most of them are sampling noise, and the most stable one is not about crungi at all.

Measuring reproducibility by resampling disjoint halves of the archive and comparing the resulting bases:

- **pixel space**: components 1-5 hold up (|cos| = 1.00, 0.96, 0.91, 0.90, 0.81), then it falls off a cliff — component 7 is 0.37 and components 9-24 average 0.29. Only 3 of 24 clear 0.9.
- **CLIP space**: component 1 is 0.98 and component 2 is 0.92, then it collapses — component 3 is 0.22, and only 2 of 24 clear 0.9.

The cause is the eigenvalue spectrum, not the sample size. Past the first component the gaps are tiny (successive ratios of 1.05 to 1.27 in CLIP space), so components sit in near-degenerate blocks and rotate freely between samples. Restricting the ambient dimension from 512 down to 32 leaves per-component stability flat at about 0.45, so it is not a conditioning problem. More images tighten the estimates and help, but cannot manufacture gaps that are not in the data. So the hand-names past roughly the fifth component are naming a basis that a different draw of the archive would have rotated away.

Two further findings shape the fix:

- **pixel PC1 is brightness.** Its correlation with mean image brightness is r = 0.996. It is 37.7% of total variance, has a 7x eigenvalue gap to PC2, and reproduces perfectly — the most stable axis in the whole analysis, and it is a light meter. PC2-PC4 are uncontaminated (|r| <= 0.05).
- **the components are about half model identity.** As an ANOVA over model labels, CLIP PC1 is 63% model identity and PC2 is 57%, with a mean of 0.46 across all 24. The archive's principal axes of variation are substantially the models, not the creature. That is the honest finding and extends the unalignment result already on the page rather than contradicting it.

## Design

### A supervised crungus-ness axis

Project each image onto the CLIP **text** embedding of "crungus". This axis is perfectly reproducible by construction — it does not depend on the sample at all, so no amount of resampling moves it — and it means exactly what a "crungus-ness" slider should mean. It is 46% model identity and only weakly aligned with the unsupervised basis (|r| = 0.22 with PC1, 0.41 with PC2), so it carries different information. Its extremes are legible: least crungus is ideogram's output, most crungus is recraft's SVG.

Add it to `eigen.json` as a first-class axis alongside the components: `text_axis: { prompt, vector, sigma, positive, negative }`, with the same exemplar convention the components use. On the page it becomes the headline slider, above the numbered ones.

### Truncate the named components

- keep computing 24 components, but only **name** those that survive resampling. Add a `stability` field per component: the mean |cos| between that component and its counterpart from disjoint-half resampling, averaged over 8 splits, computed at build time.
- `data/eigen-names.toml` keeps names only for components whose stability exceeds 0.7; the rest render as "component N" on the page. Document the threshold in the file header.
- do **not** varimax-rotate. It was measured: on the CLIP top-24 basis with optimal matching between halves, varimax lifts mean |cos| from 0.611 to 0.706 and axes above 0.7 from 8 to 12, but drops axes above 0.9 from 2 to **zero**, because it rotates PC1 and PC2 into the mixture. Since the goal is a small number of strong axes rather than a dozen soft ones, the PCA basis is the right one. Record this decision so it is not relitigated.

### Show the stability

Put the per-component stability number on the page next to each slider, and say in the copy what it means: this axis reproduces (or does not) when the archive is resampled. "These five axes survive resampling and these nineteen do not" is exactly the kind of result the project exists to show, and it is honest about what the sliders past the fifth are doing.

Also state on the page and in the about section that pixel component 1 is brightness (r = 0.996) and that the components are roughly half model identity.

### Verification

- a test pins the stability computation: on a synthetic matrix with a known planted spectrum, planted directions score high and the degenerate tail scores low.
- a test that the text axis is stable under resampling by construction (it does not depend on the rows at all).
- site checks green; vitest covers the text-axis slider arithmetic alongside the existing component maths.
- `agent-browser` smoke test on `/eigen/`: the crungus-ness slider moves the reconstruction, and unnamed components render as "component N" with their stability shown.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 eigen.json carries a per-component stability score: mean |cos| against the counterpart component from disjoint-half resampling over 8 splits, computed at build time
- [ ] #2 eigen.json carries a text_axis built by projecting each image onto the CLIP text embedding of crungus, with sigma and exemplars at each extreme in the same convention as the components
- [ ] #3 /eigen/ shows the crungus-ness slider as the headline axis above the numbered components, and moving it changes the reconstruction
- [ ] #4 components with stability at or below 0.7 render as component N rather than a hand-name, and eigen-names.toml documents the threshold
- [ ] #5 each component row shows its stability score, and the copy explains what resampling stability means
- [ ] #6 the page and about section state that pixel component 1 is brightness (r = 0.996) and that the components are roughly half model identity
- [ ] #7 the PCA basis is kept unrotated and the decision against varimax is recorded with its measured trade-off
- [ ] #8 tests cover the stability computation against a planted spectrum and the text-axis slider arithmetic; all pipeline and site checks are green
<!-- AC:END -->
