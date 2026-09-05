"""CLIP/CLAP embeddings → crungus-ness scores and UMAP atlas coordinates.

Local and free: open-clip ViT-B/32 over the images and LAION CLAP over the
clips, cached in state/embeddings.npz and state/audio-embeddings.npz (keyed
by relative path sans extension). The crungus-ness score of a (model, prompt)
set is the mean pairwise cosine similarity of its embeddings — high means the
model renders a consistent creature (or sound), the defining property of the
original 2022 crungus. UMAP projects the image embeddings to 2D for the
atlas, normalised to [0, 1]².
"""

import subprocess
from pathlib import Path

import numpy as np
from loguru import logger
from pydantic import BaseModel

from .config import Settings

CLIP_MODEL = "ViT-B-32"
CLIP_PRETRAINED = "openai"
BATCH_SIZE = 64
CLAP_MODEL = "laion/clap-htsat-unfused"
CLAP_SAMPLE_RATE = 48000
# CLAP's native input is 10 s; longer clips are embedded window by window
# and averaged (the unfused model would otherwise take a random crop)
CLAP_WINDOW = 10 * CLAP_SAMPLE_RATE


class Analysis(BaseModel):
    consistency: dict[str, float]  # "<slug>/<prompt_slug>" -> mean pairwise cos sim
    atlas: dict[str, tuple[float, float]]  # "<slug>/<prompt_slug>/<index>" -> x, y
    # "<slug>/<prompt_slug>/<index>" -> mean cos sim to all same-release-year
    # images: how typical this image is of its year's crungus
    year_typicality: dict[str, float] = {}


def analysis_path(settings: Settings) -> Path:
    return settings.state_dir / "analysis.json"


def load_embeddings(path: Path) -> dict[str, np.ndarray]:
    if not path.exists():
        return {}
    with np.load(path) as data:
        return {key: data[key] for key in data.files}


def save_embeddings(path: Path, embeddings: dict[str, np.ndarray]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, allow_pickle=False, **embeddings)


def embed_images(settings: Settings) -> dict[str, np.ndarray]:
    """Embed every optimized image, reusing cached embeddings.

    The optimized tree is the source (not originals): it is guaranteed raster
    (SVG outputs get rasterised by optimize) and Pillow reads AVIF natively.
    """
    import open_clip
    import torch
    from PIL import Image

    embeddings = load_embeddings(settings.embeddings_path)
    all_images = sorted(settings.optimized_dir.rglob("*.avif"))
    pending = [
        p
        for p in all_images
        if str(p.relative_to(settings.optimized_dir).with_suffix("")) not in embeddings
    ]
    logger.info("embeddings: {} cached, {} to compute", len(embeddings), len(pending))
    if not pending:
        return embeddings

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, _, preprocess = open_clip.create_model_and_transforms(
        CLIP_MODEL, pretrained=CLIP_PRETRAINED, device=device
    )
    model.eval()

    for start in range(0, len(pending), BATCH_SIZE):
        batch_paths = pending[start : start + BATCH_SIZE]
        tensors = []
        for p in batch_paths:
            with Image.open(p) as img:
                tensors.append(preprocess(img.convert("RGB")))
        batch = torch.stack(tensors).to(device)
        with torch.no_grad():
            features = model.encode_image(batch)
            features = features / features.norm(dim=-1, keepdim=True)
        for p, vector in zip(batch_paths, features.cpu().numpy(), strict=True):
            key = str(p.relative_to(settings.optimized_dir).with_suffix(""))
            embeddings[key] = vector.astype(np.float32)
        logger.info(
            "embedded {}/{}", min(start + BATCH_SIZE, len(pending)), len(pending)
        )

    save_embeddings(settings.embeddings_path, embeddings)
    return embeddings


def decode_clip(path: Path) -> np.ndarray:
    """Decode any audio file to 48 kHz mono float32 via ffmpeg."""
    raw = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-f",
            "f32le",
            "-ac",
            "1",
            "-ar",
            str(CLAP_SAMPLE_RATE),
            "-",
        ],
        check=True,
        capture_output=True,
    ).stdout
    return np.frombuffer(raw, dtype=np.float32)


def windows(audio: np.ndarray, size: int = CLAP_WINDOW) -> list[np.ndarray]:
    """Consecutive windows covering the whole clip; a short clip is one window."""
    if len(audio) <= size:
        return [audio]
    return [audio[start : start + size] for start in range(0, len(audio), size)]


def embed_clips(settings: Settings) -> dict[str, np.ndarray]:
    """Embed every optimized clip with CLAP, reusing cached embeddings."""
    import torch
    from transformers import ClapModel, ClapProcessor

    embeddings = load_embeddings(settings.audio_embeddings_path)
    all_clips = sorted(settings.optimized_dir.rglob("*.opus"))
    pending = [
        p
        for p in all_clips
        if str(p.relative_to(settings.optimized_dir).with_suffix("")) not in embeddings
    ]
    logger.info(
        "audio embeddings: {} cached, {} to compute", len(embeddings), len(pending)
    )
    if not pending:
        return embeddings

    model = ClapModel.from_pretrained(CLAP_MODEL).eval()
    processor = ClapProcessor.from_pretrained(CLAP_MODEL)
    for i, path in enumerate(pending, 1):
        inputs = processor(
            audio=windows(decode_clip(path)),
            sampling_rate=CLAP_SAMPLE_RATE,
            return_tensors="pt",
            padding=True,
        )
        with torch.no_grad():
            per_window = model.get_audio_features(**inputs).pooler_output
        vector = per_window.mean(dim=0)
        vector = vector / vector.norm()
        key = str(path.relative_to(settings.optimized_dir).with_suffix(""))
        embeddings[key] = vector.numpy().astype(np.float32)
        if i % 25 == 0 or i == len(pending):
            logger.info("embedded clips {}/{}", i, len(pending))

    save_embeddings(settings.audio_embeddings_path, embeddings)
    return embeddings


def consistency_scores(embeddings: dict[str, np.ndarray]) -> dict[str, float]:
    """Mean pairwise cosine similarity per <slug>/<prompt_slug> group."""
    groups: dict[str, list[np.ndarray]] = {}
    for key, vector in embeddings.items():
        group = key.rsplit("/", 1)[0]
        groups.setdefault(group, []).append(vector)

    scores: dict[str, float] = {}
    for group, vectors in groups.items():
        if len(vectors) < 2:
            continue
        matrix = np.stack(vectors)  # already L2-normalised
        sims = matrix @ matrix.T
        n = len(vectors)
        off_diagonal = (sims.sum() - np.trace(sims)) / (n * (n - 1))
        scores[group] = round(float(off_diagonal), 4)
    return scores


def atlas_coords(embeddings: dict[str, np.ndarray]) -> dict[str, tuple[float, float]]:
    """UMAP to 2D, normalised to [0, 1]²."""
    import umap

    keys = sorted(embeddings)
    matrix = np.stack([embeddings[k] for k in keys])
    # n_jobs=1 explicitly: random_state forces serial anyway, and leaving the
    # default -1 makes umap emit an override warning
    reducer = umap.UMAP(
        n_neighbors=15, min_dist=0.1, metric="cosine", random_state=42, n_jobs=1
    )
    coords = reducer.fit_transform(matrix)
    low = coords.min(axis=0)
    span = coords.max(axis=0) - low
    span[span == 0] = 1.0
    normalised = (coords - low) / span
    return {
        key: (round(float(x), 4), round(float(y), 4))
        for key, (x, y) in zip(keys, normalised, strict=True)
    }


def year_typicality_scores(
    embeddings: dict[str, np.ndarray], year_of_slug: dict[str, str]
) -> dict[str, float]:
    """Mean cosine similarity of each image to every image of its release year."""
    by_year: dict[str, list[str]] = {}
    for key in embeddings:
        year = year_of_slug.get(key.split("/", 1)[0])
        if year is not None:
            by_year.setdefault(year, []).append(key)

    scores: dict[str, float] = {}
    for keys in by_year.values():
        if len(keys) < 2:
            continue
        matrix = np.stack([embeddings[k] for k in keys])
        sims = matrix @ matrix.T
        n = len(keys)
        means = (sims.sum(axis=1) - 1.0) / (n - 1)  # exclude self-similarity
        for key, value in zip(keys, means, strict=True):
            scores[key] = round(float(value), 4)
    return scores


def _release_years(settings: Settings) -> dict[str, str]:
    from .registry import load_registry

    registry = load_registry(settings.registry_path)
    if registry is None:
        return {}
    years: dict[str, str] = {}
    for model in registry.models:
        date = model.release_date or (
            model.version_created_at.date() if model.version_created_at else None
        )
        if date is not None:
            years[model.slug] = str(date.year)
    return years


def run_analysis(settings: Settings) -> Analysis:
    embeddings = embed_images(settings)
    clip_embeddings = embed_clips(settings)
    if not embeddings and not clip_embeddings:
        logger.warning("nothing to analyse")
        return Analysis(consistency={}, atlas={})
    # image and audio keys never collide: each model has one modality
    analysis = Analysis(
        consistency=consistency_scores(embeddings)
        | consistency_scores(clip_embeddings),
        atlas=atlas_coords(embeddings) if embeddings else {},
        year_typicality=year_typicality_scores(embeddings, _release_years(settings)),
    )
    path = analysis_path(settings)
    path.write_text(analysis.model_dump_json(indent=2) + "\n")
    logger.info(
        "analysis: {} groups scored, {} atlas points → {}",
        len(analysis.consistency),
        len(analysis.atlas),
        path,
    )
    return analysis


def load_analysis(settings: Settings) -> Analysis | None:
    path = analysis_path(settings)
    if not path.exists():
        return None
    return Analysis.model_validate_json(path.read_text())
