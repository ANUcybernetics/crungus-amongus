"""Semantic eigencrungi: PCA over the archive in CLIP embedding space.

The pixel decomposition in eigen.py finds what a photograph of a crungus looks
like: its leading axis is a light meter (r = 0.9967 with mean brightness). This
one decomposes the same archive in the embedding space of open-clip's
ViT-bigG-14, where distance is semantic, so the axes are closer to
photoreal-versus-illustration than to bright-versus-dark. The measured case for
that space: under disjoint-half resampling its top-24 subspace overlap is 0.970
against 0.751 for pixels.

An axis in a 1280-d embedding space is not a picture, so each retained one is
*rendered*. Kandinsky 2.2's decoder conditions directly on a ViT-bigG-14 image
embedding, which makes it the one model that can be handed a point on a
principal component and asked what it looks like. It is also one of the
archive's own models, which is the reason to be careful about how the result is
read: a filmstrip is Kandinsky's guess at what lies along the axis, not the
archive's ground truth. The nearest real images are the ground truth, and the
page shows both.

Embeddings are cached unnormalised (see analyzer.SEMANTIC_CLIP) and the
decomposition runs on them at that native scale, because mean + kσ·component
has to land somewhere the decoder recognises. Cosines against the text
embedding normalise on the way in.

Outputs, under data/derived/eigen-clip/ so that nothing here can feed itself
back into the corpus it came from:

- eigen-clip.json — per axis: variance share, coefficient σ, resampling
  stability, filmstrip frame keys and the archive's exemplars at each extreme;
  plus every image's coefficients in σ units
- mean.avif, c01/*.avif, ... — the filmstrips (written by render_filmstrips)

and state/eigen-clip.npz, the basis itself, which only the renderer needs.
"""

import json
from pathlib import Path

import numpy as np
from loguru import logger

from .config import Settings
from .eigen import (
    COMPONENTS,
    EXEMPLARS,
    STABILITY_SPLITS,
    STABILITY_THRESHOLD,
    TEXT_PROMPT,
    load_names,
    pca,
    stability,
    supervised_direction,
)

# frames per filmstrip, spanning ±SIGMA_SPAN. Odd, so the centre frame is the
# mean crungus itself and every axis shares it.
FILMSTRIP_STEPS = 7
SIGMA_SPAN = 3.0
DERIVED_SUBDIR = "eigen-clip"
MEAN_FRAME = "mean.avif"


def frame_offsets() -> np.ndarray:
    """Each frame's position along an axis, in σ."""
    return np.linspace(-SIGMA_SPAN, SIGMA_SPAN, FILMSTRIP_STEPS)


def frame_for_sigma(position: float) -> int:
    """The filmstrip frame nearest a slider position in σ.

    Monotone in `position` and clamped to the strip, so a slider dragged past
    ±3σ holds on the end frame rather than wrapping.
    """
    step = (FILMSTRIP_STEPS - 1) / (2 * SIGMA_SPAN)
    index = round((position + SIGMA_SPAN) * step)
    return max(0, min(FILMSTRIP_STEPS - 1, int(index)))


def component_dir(index: int) -> str:
    """Frame directory for a 1-based component number."""
    return f"c{index:02d}"


def frame_keys(directory: str) -> list[str]:
    """Bucket keys for one axis's frames; the centre is the shared mean."""
    return [
        f"{DERIVED_SUBDIR}/{MEAN_FRAME}"
        if i == FILMSTRIP_STEPS // 2
        else f"{DERIVED_SUBDIR}/{directory}/{i}.avif"
        for i in range(FILMSTRIP_STEPS)
    ]


def basis_path(settings: Settings) -> Path:
    return settings.state_dir / "eigen-clip.npz"


def output_dir(settings: Settings) -> Path:
    return settings.derived_dir / DERIVED_SUBDIR


def corpus_rows(
    settings: Settings, embeddings: dict[str, np.ndarray]
) -> tuple[list[str], np.ndarray]:
    """Image keys in the same order as the pixel sheet, and their embeddings.

    Keyed on the optimized tree rather than on the cache, so a stale cache
    entry for a deleted image cannot slip into the decomposition.
    """
    files = sorted(settings.optimized_dir.rglob("*.avif"))
    keys = [str(p.relative_to(settings.optimized_dir)) for p in files]
    missing = [key for key in keys if key.rsplit(".", 1)[0] not in embeddings]
    if missing:
        raise RuntimeError(
            f"{len(missing)} optimized images have no ViT-bigG-14 embedding "
            f"(first: {missing[0]})"
        )
    rows = np.stack([embeddings[key.rsplit(".", 1)[0]] for key in keys])
    return keys, rows


def build_clip_eigen(settings: Settings) -> None:
    """Decompose the archive's ViT-bigG-14 embeddings; write the basis and payload."""
    from .analyzer import SEMANTIC_CLIP, embed_images, embed_text, unit_rows

    embeddings = embed_images(settings, SEMANTIC_CLIP)
    keys, rows = corpus_rows(settings, embeddings)
    norms = np.linalg.norm(rows, axis=1)
    logger.info(
        "eigen-clip: {} images, embedding norm {:.1f} ± {:.1f}",
        len(keys),
        float(norms.mean()),
        float(norms.std()),
    )

    result = pca(rows, COMPONENTS)
    k = result.components.shape[0]
    scores = stability(rows, k)
    retained = int((scores > STABILITY_THRESHOLD).sum())
    logger.info(
        "eigen-clip: {} components explain {:.0%} of variance, {}/{} reproduce above {}",
        k,
        float(result.variance_ratio.sum()),
        retained,
        k,
        STABILITY_THRESHOLD,
    )

    names = load_names(settings.eigen_names_path, table="clip")
    sigma = result.coefficients.std(axis=0)
    components: list[dict[str, object]] = []
    for j in range(k):
        keep = bool(scores[j] > STABILITY_THRESHOLD)
        order = np.argsort(result.coefficients[:, j])
        components.append(
            {
                "variance": round(float(result.variance_ratio[j]), 4),
                "sigma": float(sigma[j]),
                "stability": round(float(scores[j]), 3),
                # naming, and rendering, an axis below the threshold would be
                # describing this draw of the archive rather than the archive
                "name": names.get(j + 1) if keep else None,
                "frames": frame_keys(component_dir(j + 1)) if keep else None,
                "positive": [keys[i] for i in order[::-1][:EXEMPLARS]],
                "negative": [keys[i] for i in order[:EXEMPLARS]],
            }
        )

    text_vector = embed_text(TEXT_PROMPT, SEMANTIC_CLIP)
    similarity = unit_rows(rows) @ text_vector
    direction, z = supervised_direction(rows, similarity)
    order = np.argsort(z)
    text_axis = {
        "prompt": TEXT_PROMPT,
        "sigma": float(np.linalg.norm(direction)),
        # fixed by the prompt, not by the sample: resampling cannot move it
        "stability": 1.0,
        "similarity_mean": round(float(similarity.mean()), 4),
        "similarity_sigma": round(float(similarity.std()), 4),
        "frames": frame_keys("text"),
        "positive": [keys[i] for i in order[::-1][:EXEMPLARS]],
        "negative": [keys[i] for i in order[:EXEMPLARS]],
    }
    logger.info(
        "eigen-clip: crungus-ness axis, cosine {:.3f} ± {:.3f}",
        float(similarity.mean()),
        float(similarity.std()),
    )

    standardised = result.coefficients / sigma
    payload = {
        "space": f"{SEMANTIC_CLIP.model}/{SEMANTIC_CLIP.pretrained}",
        "image_count": len(keys),
        "stability_threshold": STABILITY_THRESHOLD,
        "stability_splits": STABILITY_SPLITS,
        "filmstrip_steps": FILMSTRIP_STEPS,
        "sigma_span": SIGMA_SPAN,
        "components": components,
        "text_axis": text_axis,
        "coefficients": {
            key: [round(float(v), 2) for v in standardised[i]]
            for i, key in enumerate(keys)
        },
        "text_coefficients": {key: round(float(z[i]), 2) for i, key in enumerate(keys)},
    }

    out = output_dir(settings)
    out.mkdir(parents=True, exist_ok=True)
    (out / "eigen-clip.json").write_text(json.dumps(payload) + "\n")
    np.savez_compressed(
        basis_path(settings),
        allow_pickle=False,
        mean=result.mean,
        components=result.components,
        sigma=sigma,
        text_direction=direction,
        stability=scores,
    )
    logger.info(
        "eigen-clip: {} axes to render → {}", retained + 1, out / "eigen-clip.json"
    )
