# crungus amongus

An archive of the [crungus](https://en.wikipedia.org/wiki/Crungus) — the
creature that text-to-image models summon from a made-up word — recorded across
~90 Replicate models from DALL·E mini (2022) to the present.

Two components:

- **`pipeline/`** — a Python batch tool (`crungus`) that discovers models,
  generates images, encodes them to AVIF, scores each model's consistency with
  CLIP, projects an embedding atlas with UMAP, uploads to a Tigris bucket, and
  emits the site's data contract
- **`site/`** — an Astro static site that presents the archive, per-model pages,
  and the pan/zoom embedding atlas

## Pipeline

Requires `REPLICATE_API_TOKEN`, and `CRUNGUS_S3_*` credentials for `sync` (all
provided via the untracked mise `[env]` block). Stages are sequential,
idempotent, and resumable:

```sh
cd pipeline
uv run crungus discover   # pin models from the collection + data/curated-models.toml
uv run crungus generate   # run predictions (spends money; see --dry-run, --budget flags)
uv run crungus optimize   # originals → AVIF
uv run crungus analyze    # CLIP embeddings → consistency scores + atlas coords
uv run crungus sprite     # atlas sprite sheet for the site
uv run crungus sync       # upload AVIFs to the public bucket
uv run crungus publish    # write site/src/data/models.json
uv run crungus status     # progress/spend summary
```

Checks:
`uv run ruff check . && uv run ruff format --check . && uvx ty check && uv run pytest`

## Site

```sh
cd site
pnpm install
pnpm run sync-images   # pull the image corpus from the public bucket
pnpm run dev
```

Checks:
`pnpm run typecheck && pnpm run lint && pnpm run lint:css && pnpm run format:check && pnpm run test && pnpm run build`

Deploys to GitHub Pages on push to `main`; CI pulls images from the bucket (no
credentials needed — it's public-read) and caches them keyed on the data
contract.
