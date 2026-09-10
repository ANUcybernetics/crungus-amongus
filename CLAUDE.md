# crungus-amongus

Archive of "crungus" images and audio clips generated across Replicate models,
plus the Astro site that presents them. `README.md` has the layout, the
stage-by-stage pipeline commands and the check commands for both halves; run
them with `mise exec --`.

## Constraints

- `crungus generate` spends real money. Never run it unless asked; always
  `--dry-run` first and report the estimate.
- Model version pins in `state/models.json` are sticky: a bump orphans that
  model's outputs and implies re-spend. Only `discover --refresh-versions` may
  bump them, and only when asked.
- `state/manifest.jsonl` is append-only provenance. Never edit or squash it.
- Generated media never goes in git. It lives under `data/` and in the public
  Tigris bucket. Corpus keys embed the pinned model version and are served
  immutable-cached, so changed content needs a new key, not an overwrite;
  anything recomputed at a stable key ships with a short cache instead (see
  `bucket_sync.upload_plan`).
- `analyze`, `sprite` and `eigen` all glob `data/optimized/**.avif`, so an image
  the pipeline *renders* and stores there silently joins the corpus it was
  derived from. Renders go in `data/derived/`, the sync's second root.
- `site/src/data/models.json` is the contract between the halves: written by
  `crungus publish` (pydantic), parsed by `site/src/lib/schema.ts` (zod). Change
  both together or neither, and keep `publish`'s output a fixed point of oxfmt
  (see `inline_short_arrays` in `site_export.py`).
- The prompt sets and sample counts in `config.py` are the experiments' fixed
  methodology. Changing them invalidates cross-model comparison, so don't.
