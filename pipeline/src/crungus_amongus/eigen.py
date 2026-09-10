"""Eigencrungi: PCA over the archive in pixel space, eigenfaces-style.

Every optimized image is centre-cropped, shrunk to SIDE×SIDE RGB and flattened
to a row; the principal components of that matrix are the eigencrungi. Nothing
aligns a crungus the way eyes and mouths align a face, so the leading
components encode framing, palette and light before they encode a creature —
which is the finding, not a bug.

The decomposition is a randomised SVD. Turk & Pentland's trick — eigenvectors
of the small N×N Gram matrix — is the right algorithm only while N is much
smaller than D, and at corpus scale it stops being: a centred copy of the rows
plus an N×N Gram matrix runs to several gigabytes at N = 16 000. The randomised
range finder never materialises either, so peak memory is the rows themselves
plus a few narrow blocks, and the top components agree with the exact
decomposition to about 1e-6 on this archive.

Not every component is real, so the sheet ships a reproducibility score
alongside each one. `stability` splits the archive into disjoint halves,
decomposes each and takes |cos| between the two bases component by component.
Only components above STABILITY_THRESHOLD are given a name.

How many survive turns out to be a question about sample size, not about the
spectrum. At 1594 images five components cleared 0.7 and the collapse looked
structural — the eigenvalues past the fifth sit close enough together to leave
their components free to rotate. At 19 344 images nineteen clear 0.7 and
thirteen clear 0.9. Ten times the data bought fourteen more real axes, so read
a low score here as "not enough images yet" before reading it as "no such
direction".

The basis is deliberately left unrotated. Varimax was measured on the CLIP
top-24 basis: with optimal matching between halves it lifts mean |cos| from
0.611 to 0.706 and axes above 0.7 from 8 to 12, but it drops axes above 0.9
from 2 to zero, because it rotates the two reproducible components into the
mixture. A few strong axes beat a dozen soft ones here, so PCA stands.

Two facts about the unsupervised basis set the terms for the supervised one:
pixel component 1 correlates with mean image brightness at r = 0.9967 (the most
reproducible axis in the archive is a light meter), and as an ANOVA over model
labels it is 54% model identity against 16% across all 24. So the sheet also carries a
supervised axis: every image projected onto the CLIP *text* embedding of
"crungus", rendered into pixel space by least squares. That axis is fixed by
the prompt rather than by the sample, so no amount of resampling can rotate it,
and it means what a crungus-ness slider should mean.

Output lands in the optimized tree so `sync` ships it to the bucket and the
site's /eigen/ page fetches it at runtime:

- eigen.webp — a lossless sheet of SIDE×SIDE tiles: the mean crungus, one tile
  per component, then the supervised axis, quantised to bytes centred on 128
  (see quantise)
- eigen.json — per axis: dequantisation scale, the coefficient's standard
  deviation, resampling stability, its tile index and the archive's exemplars
  at each extreme; components add their variance share and hand-given name
  (data/eigen-names.toml); plus every image's coefficients in
  standard-deviation units, so the page can put any real crungus on the sliders
"""

import json
import tomllib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from loguru import logger
from PIL import Image

from .config import Settings
from .sprite import square

SIDE = 128
COMPONENTS = 24
EXEMPLARS = 3
# disjoint-half resamples averaged into each component's stability score
STABILITY_SPLITS = 8
# a component below this is sampling noise, and goes unnamed on the site
STABILITY_THRESHOLD = 0.7
# the supervised axis: images projected onto this prompt's CLIP text embedding
TEXT_PROMPT = "crungus"
# randomised SVD: extra sampled directions and power iterations. Generous on
# both, because the archive's spectrum is nearly flat past the leading few and
# a thin sketch there returns a rotation of the true components rather than the
# components. These values pin the top COMPONENTS to the exact decomposition to
# about 1e-6, for a couple of seconds at the current corpus size.
OVERSAMPLING = 32
POWER_ITERATIONS = 8
# rows per block when accumulating total variance, bounding the temporary
VARIANCE_BLOCK = 1024


@dataclass
class Pca:
    mean: np.ndarray  # (D,)
    components: np.ndarray  # (k, D), orthonormal rows
    coefficients: np.ndarray  # (N, k), projection of each centred row
    variance_ratio: np.ndarray  # (k,), share of total variance


def total_variance(rows: np.ndarray, mean: np.ndarray) -> float:
    """Σ‖row − mean‖², accumulated a block at a time so nothing is copied whole."""
    total = 0.0
    for start in range(0, len(rows), VARIANCE_BLOCK):
        block = rows[start : start + VARIANCE_BLOCK] - mean
        total += float(np.einsum("ij,ij->", block, block, dtype=np.float64))
    return total


def pca(rows: np.ndarray, k: int) -> Pca:
    """Top-k principal components of rows (N×D) by randomised SVD.

    The centred matrix is never formed: every product with it is written in
    terms of the rows and their mean, so the working set is the rows plus a few
    N×ℓ and D×ℓ blocks. The sketch is seeded fixed, so a build is reproducible.

    Each component's sign is fixed so that the image projecting furthest along
    it projects positively — the "+" end is the archive's extreme.
    """
    n, d = rows.shape
    k = min(k, n - 1)
    mean = rows.mean(axis=0)
    # ℓ cannot usefully exceed the centred matrix's rank, which is n − 1
    width = min(k + OVERSAMPLING, n - 1, d)
    rng = np.random.default_rng(0)

    def forward(x: np.ndarray) -> np.ndarray:
        """(rows − mean) @ x"""
        return rows @ x - mean @ x

    def backward(x: np.ndarray) -> np.ndarray:
        """(rows − mean).T @ x"""
        return rows.T @ x - np.outer(mean, x.sum(axis=0))

    sketch = rng.standard_normal((d, width)).astype(rows.dtype)
    basis, _ = np.linalg.qr(forward(sketch))
    for _ in range(POWER_ITERATIONS):
        rotated, _ = np.linalg.qr(backward(basis))
        basis, _ = np.linalg.qr(forward(rotated))
    left, singular, right = np.linalg.svd(backward(basis).T, full_matrices=False)

    components = right[:k]
    coefficients = (basis @ left)[:, :k] * singular[:k]
    for j in range(k):
        if coefficients[np.argmax(np.abs(coefficients[:, j])), j] < 0:
            components[j] *= -1
            coefficients[:, j] *= -1
    eigenvalues = singular[:k].astype(np.float64) ** 2
    return Pca(
        mean=mean,
        components=components,
        coefficients=coefficients,
        variance_ratio=(eigenvalues / total_variance(rows, mean)).astype(np.float32),
    )


def stability(
    rows: np.ndarray, k: int, splits: int = STABILITY_SPLITS, seed: int = 0
) -> np.ndarray:
    """How well each of the top k components reproduces on a fresh draw.

    Each split shuffles the rows, decomposes two disjoint halves and takes
    |cos| between the two bases component by component; the score is the mean
    over splits. 1 means the direction is a property of the archive, and a
    number near zero means it is a property of this particular sample.

    A half of the archive has rank one less than its row count, so on a small
    archive it cannot offer all k components to compare against. Those score
    zero, which is the right reading: there are not enough images to tell.
    """
    rng = np.random.default_rng(seed)
    n = rows.shape[0]
    half = n // 2
    width = max(0, min(k, half - 1))
    total = np.zeros(k, dtype=np.float64)
    for _ in range(splits):
        order = rng.permutation(n)
        left = pca(rows[order[:half]], width).components
        right = pca(rows[order[half : 2 * half]], width).components
        total[:width] += np.abs(np.sum(left * right, axis=1))
    return (total / splits).astype(np.float32)


def supervised_direction(
    rows: np.ndarray, score: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Least-squares pixel direction per σ of a supervised score, and the score in σ.

    Standardising the score makes Σz² = N, so the regression slope is just the
    score-weighted mean of the rows — and since Σz = 0 it needs no centring.
    """
    z = (score - score.mean()) / score.std()
    return (z @ rows) / len(z), z.astype(np.float32)


def quantise(component: np.ndarray) -> tuple[np.ndarray, float]:
    """Map a zero-centred vector to bytes around 128; returns (bytes, scale)."""
    scale = float(np.abs(component).max()) or 1.0
    q = np.rint(128 + 127 * component / scale).clip(1, 255).astype(np.uint8)
    return q, scale


def dequantise(q: np.ndarray, scale: float) -> np.ndarray:
    return (q.astype(np.float32) - 128) / 127 * scale


def load_names(path: Path, table: str = "names") -> dict[int, str]:
    """Hand-given component names for one basis, 1-based index → name."""
    if not path.exists():
        return {}
    entries = tomllib.loads(path.read_text()).get(table, {})
    return {int(i): name for i, name in entries.items()}


def load_pixels(files: list[Path], side: int) -> np.ndarray:
    rows = np.empty((len(files), side * side * 3), dtype=np.float32)
    for i, path in enumerate(files):
        with Image.open(path) as img:
            rows[i] = np.asarray(square(img, side), dtype=np.float32).ravel() / 255
    return rows


def text_scores(
    settings: Settings, keys: list[str]
) -> tuple[np.ndarray, np.ndarray] | None:
    """(CLIP text embedding of TEXT_PROMPT, its cosine with every key's image).

    None when `analyze` has not embedded the whole corpus yet: the supervised
    axis is then simply left out rather than holding up the rest of the sheet.
    """
    from .analyzer import ATLAS_CLIP, cache_path, embed_text, load_embeddings

    embeddings = load_embeddings(cache_path(settings, ATLAS_CLIP))
    stems = [key.rsplit(".", 1)[0] for key in keys]
    missing = [stem for stem in stems if stem not in embeddings]
    if missing:
        logger.warning(
            "eigen: {} images have no CLIP embedding — run analyze for the "
            "crungus-ness axis",
            len(missing),
        )
        return None
    vector = embed_text(TEXT_PROMPT)
    return vector, np.stack([embeddings[stem] for stem in stems]) @ vector


def build_eigen(settings: Settings, out_dir: Path | None = None) -> Pca | None:
    """Decompose data/optimized/**.avif into eigen.webp + eigen.json."""
    if out_dir is None:
        out_dir = settings.optimized_dir / "eigen"
    files = sorted(settings.optimized_dir.rglob("*.avif"))
    keys = [str(p.relative_to(settings.optimized_dir)) for p in files]
    if len(keys) < 2:
        logger.warning("eigen: not enough optimized images")
        return None

    logger.info("eigen: loading {} images at {}px", len(keys), SIDE)
    rows = load_pixels(files, SIDE)
    result = pca(rows, COMPONENTS)
    k = result.components.shape[0]
    logger.info(
        "eigen: {} components explain {:.0%} of variance",
        k,
        float(result.variance_ratio.sum()),
    )
    scores = stability(rows, k)
    logger.info(
        "eigen: {}/{} components reproduce above {}",
        int((scores > STABILITY_THRESHOLD).sum()),
        k,
        STABILITY_THRESHOLD,
    )

    names = load_names(settings.eigen_names_path)
    sigma = result.coefficients.std(axis=0)
    tiles = [np.rint(result.mean * 255).astype(np.uint8)]
    components: list[dict[str, object]] = []
    for j in range(k):
        q, scale = quantise(result.components[j])
        tiles.append(q)
        order = np.argsort(result.coefficients[:, j])
        components.append(
            {
                "tile": len(tiles) - 1,
                "variance": round(float(result.variance_ratio[j]), 4),
                "scale": scale,
                "sigma": float(sigma[j]),
                "stability": round(float(scores[j]), 3),
                # a name past the threshold would be naming this draw of the
                # archive rather than the archive
                "name": names.get(j + 1) if scores[j] > STABILITY_THRESHOLD else None,
                "positive": [keys[i] for i in order[::-1][:EXEMPLARS]],
                "negative": [keys[i] for i in order[:EXEMPLARS]],
            }
        )
    standardised = result.coefficients / sigma
    payload: dict[str, object] = {
        "side": SIDE,
        "image_count": len(keys),
        "stability_threshold": STABILITY_THRESHOLD,
        "stability_splits": STABILITY_SPLITS,
        "components": components,
        "coefficients": {
            key: [round(float(v), 2) for v in standardised[i]]
            for i, key in enumerate(keys)
        },
    }

    scored = text_scores(settings, keys)
    if scored is not None:
        vector, similarity = scored
        direction, z = supervised_direction(rows, similarity)
        length = float(np.linalg.norm(direction))
        q, scale = quantise(direction / length)
        tiles.append(q)
        order = np.argsort(z)
        payload["text_axis"] = {
            "prompt": TEXT_PROMPT,
            "tile": len(tiles) - 1,
            "vector": [round(float(v), 6) for v in vector],
            "scale": scale,
            "sigma": length,
            # fixed by the prompt, not by the sample: resampling cannot move it
            "stability": 1.0,
            "similarity_mean": round(float(similarity.mean()), 4),
            "similarity_sigma": round(float(similarity.std()), 4),
            "positive": [keys[i] for i in order[::-1][:EXEMPLARS]],
            "negative": [keys[i] for i in order[:EXEMPLARS]],
        }
        payload["text_coefficients"] = {
            key: round(float(z[i]), 2) for i, key in enumerate(keys)
        }
        logger.info(
            "eigen: crungus-ness axis, cosine {:.3f} ± {:.3f}",
            float(similarity.mean()),
            float(similarity.std()),
        )

    sheet = Image.new("RGB", (SIDE * len(tiles), SIDE))
    for i, tile in enumerate(tiles):
        sheet.paste(_tile(tile), (SIDE * i, 0))

    out_dir.mkdir(parents=True, exist_ok=True)
    sheet.save(out_dir / "eigen.webp", format="WEBP", lossless=True, method=6)
    (out_dir / "eigen.json").write_text(json.dumps(payload) + "\n")
    logger.info("eigen: {} tiles → {}", len(tiles), out_dir / "eigen.webp")
    return result


def _tile(flat: np.ndarray) -> Image.Image:
    return Image.fromarray(flat.reshape(SIDE, SIDE, 3), mode="RGB")
