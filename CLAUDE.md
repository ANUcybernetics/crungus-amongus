# crungus-amongus

Batch-generates images of "crungus" across Replicate text-to-image models and
publishes an Astro site exploring them. `README.md` has the stage-by-stage
pipeline commands; run them with `mise exec --` from the repo root (or inside
`pipeline/` / `site/`).

## Constraints

- `crungus generate` spends real money on the Replicate account. Never run it
  without an explicit request; always `--dry-run` first and report the estimate.
- The registry (`state/models.json`) pins model versions **stickily**; a version
  bump orphans that model's images and implies re-spend. Only
  `discover --refresh-versions` may bump pins, and only when asked.
- `state/manifest.jsonl` is append-only provenance — never edit or squash it.
- Images never go in git. Originals and optimized AVIFs live under `data/`
  (gitignored); the public corpus lives in the `crungus-amongus` Tigris bucket.
  Bucket objects are immutable-cached: changed content needs a new key, not an
  overwrite.
- The two halves share one contract: `site/src/data/models.json`, produced by
  `crungus publish` (pydantic) and parsed by `site/src/lib/schema.ts` (zod).
  Change both together or neither. `publish` emits oxfmt-formatted JSON so the
  file stays a fixed point of `site/`'s formatter; keep it one if you touch the
  writer, or every regeneration reflows the file and fails CI's `format:check`.
- The site is served from `crungusamong.us` (GitHub Pages, apex + `www`), and
  the bucket from `images.crungusamong.us` — that custom domain is
  `image_base_url` and the runtime source of the atlas sprite. Setting the Pages
  `cname` resets `https_enforced` to false; set it back once the cert issues.
- The prompt set ("crungus", "a picture of a crungus", 10 images each) is the
  experiment's fixed methodology — changing it invalidates cross-model
  comparison, so don't.
