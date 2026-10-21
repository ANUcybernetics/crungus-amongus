# crungus amongus

An archive of the [crungus](https://en.wikipedia.org/wiki/Crungus) — the
creature that text-to-image models summon from a made-up word — recorded across
~90 Replicate image models from DALL·E mini (2022) to the present, and what ~15
text-to-music and ~55 text-to-video models make of the same word.

Two components:

- **`pipeline/`** — a Python batch tool (`crungus`) that discovers models,
  generates images, sound and video clips, encodes them (AVIF; Opus with an AAC
  fallback; AV1 with an H.264 fallback and a poster frame), scores each image
  model's consistency with CLIP, projects an embedding atlas with UMAP,
  decomposes the images into eigencrungi in both pixel and CLIP space, renders
  the semantic axes with Kandinsky 2.2, reconstructs a curated handful of images
  as 3D meshes with Meshy, uploads to a Tigris bucket, and emits the site's data
  contract
- **`site/`** — an Astro static site that presents the archive, per-model pages,
  the pan/zoom embedding atlas, the eigencrungi sliders, the sound archive, the
  video archive, the mesh viewer, and the display (a full-screen wall of images,
  or one at a time, for a gallery screen, with crungus radio shuffling every
  clip over it on `?radio`)

## Pipeline

Requires `REPLICATE_API_TOKEN`, `MESHY_API_KEY` for `mesh`, and `CRUNGUS_S3_*`
credentials for `sync` (all provided via the untracked mise `[env]` block).
Stages are sequential, idempotent, and resumable:

```sh
cd pipeline
uv run crungus discover   # pin models from both collections + data/curated-*models.toml
uv run crungus generate   # run predictions (spends money; see --dry-run, --modality, --max-predictions)
uv run crungus mesh       # images listed in data/mesh-queue.toml → Meshy GLBs (spends credits; see --dry-run)
uv run crungus optimize   # originals → AVIF / Opus + AAC / compressed GLB; needs avifenc, ffmpeg, gltf-transform
uv run crungus analyze    # CLIP embeddings → consistency scores + atlas coords (images only)
uv run crungus sprite     # atlas sprite tiles for the site
uv run crungus eigen      # pixel-space PCA → eigencrungi sheet + coefficients (names: data/eigen-names.toml)
uv run crungus eigen --space clip  # CLIP-space PCA → semantic eigencrungi (embeds with ViT-bigG-14 first)
uv run crungus render     # decode the semantic axes' extremes with Kandinsky 2.2 (local GPU)
uv run crungus sync       # upload data/optimized/, data/derived/ and data/meshes/ to the public bucket
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

The build also emits a static JSON API (shapes in `src/lib/api.ts`):
`/api/models.json`, `/api/images.json`, `/api/audio.json`, `/api/videos.json`,
`/api/meshes.json` and `/api/models/<slug>.json`. Entries link to the media in
the bucket (they never embed it) and to the item's permalink, an anchor on its
model page (`src/lib/permalink.ts`).

Deploys to GitHub Pages on push to `main`; CI pulls images from the bucket (no
credentials needed — it's public-read) and caches them keyed on the data
contract.
