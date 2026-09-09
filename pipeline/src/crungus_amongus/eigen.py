"""Eigencrungi: PCA over the archive in pixel space, eigenfaces-style.

Every optimized image is centre-cropped, shrunk to SIDE×SIDE RGB and flattened
to a row; the principal components of that matrix are the eigencrungi. Nothing
aligns a crungus the way eyes and mouths align a face, so the leading
components encode framing, palette and light before they encode a creature —
which is the finding, not a bug. The decomposition uses the Turk & Pentland
trick: eigenvectors of the small N×N Gram matrix, lifted back to pixel space.

Output lands in the optimized tree so `sync` ships it to the bucket and the
site's /eigen/ page fetches it at runtime:

- eigen.webp — a lossless sheet of SIDE×SIDE tiles: the mean crungus, then one
  tile per component, quantised to bytes centred on 128 (see quantise)
- eigen.json — per component: variance share, dequantisation scale, the
  coefficient's standard deviation, hand-given name (data/eigen-names.toml) and
  the archive's exemplars at each extreme; plus every image's coefficients in
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


@dataclass
class Pca:
    mean: np.ndarray  # (D,)
    components: np.ndarray  # (k, D), orthonormal rows
    coefficients: np.ndarray  # (N, k), projection of each centred row
    variance_ratio: np.ndarray  # (k,), share of total variance


def pca(rows: np.ndarray, k: int) -> Pca:
    """Top-k principal components of rows (N×D) via the N×N Gram matrix.

    Each component's sign is fixed so that the image projecting furthest
    along it projects positively — the "+" end is the archive's extreme.
    """
    n = rows.shape[0]
    k = min(k, n - 1)
    mean = rows.mean(axis=0)
    centred = rows - mean
    gram = (centred @ centred.T).astype(np.float64)
    eigenvalues, eigenvectors = np.linalg.eigh(gram)
    order = np.argsort(eigenvalues)[::-1][:k]
    eigenvalues = np.clip(eigenvalues[order], 0, None)
    u = eigenvectors[:, order].astype(np.float32)
    singular = np.sqrt(eigenvalues).astype(np.float32)
    components = (centred.T @ u).T / singular[:, None]
    coefficients = u * singular
    for j in range(k):
        if coefficients[np.argmax(np.abs(coefficients[:, j])), j] < 0:
            components[j] *= -1
            coefficients[:, j] *= -1
    total = float(np.trace(gram))
    return Pca(
        mean=mean,
        components=components,
        coefficients=coefficients,
        variance_ratio=(eigenvalues / total).astype(np.float32),
    )


def quantise(component: np.ndarray) -> tuple[np.ndarray, float]:
    """Map a zero-centred vector to bytes around 128; returns (bytes, scale)."""
    scale = float(np.abs(component).max()) or 1.0
    q = np.rint(128 + 127 * component / scale).clip(1, 255).astype(np.uint8)
    return q, scale


def dequantise(q: np.ndarray, scale: float) -> np.ndarray:
    return (q.astype(np.float32) - 128) / 127 * scale


def load_names(path: Path) -> dict[int, str]:
    """Hand-given component names, 1-based index → name."""
    if not path.exists():
        return {}
    table = tomllib.loads(path.read_text()).get("names", {})
    return {int(i): name for i, name in table.items()}


def load_pixels(files: list[Path], side: int) -> np.ndarray:
    rows = np.empty((len(files), side * side * 3), dtype=np.float32)
    for i, path in enumerate(files):
        with Image.open(path) as img:
            rows[i] = np.asarray(square(img, side), dtype=np.float32).ravel() / 255
    return rows


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

    names = load_names(settings.eigen_names_path)
    sigma = result.coefficients.std(axis=0)
    sheet = Image.new("RGB", (SIDE * (k + 1), SIDE))
    sheet.paste(_tile(np.rint(result.mean * 255).astype(np.uint8)), (0, 0))
    components = []
    for j in range(k):
        q, scale = quantise(result.components[j])
        sheet.paste(_tile(q), (SIDE * (j + 1), 0))
        order = np.argsort(result.coefficients[:, j])
        components.append(
            {
                "variance": round(float(result.variance_ratio[j]), 4),
                "scale": scale,
                "sigma": float(sigma[j]),
                "name": names.get(j + 1),
                "positive": [keys[i] for i in order[::-1][:EXEMPLARS]],
                "negative": [keys[i] for i in order[:EXEMPLARS]],
            }
        )
    standardised = result.coefficients / sigma
    coefficients = {
        key: [round(float(v), 2) for v in standardised[i]] for i, key in enumerate(keys)
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    sheet.save(out_dir / "eigen.webp", format="WEBP", lossless=True, method=6)
    payload = {
        "side": SIDE,
        "image_count": len(keys),
        "components": components,
        "coefficients": coefficients,
    }
    (out_dir / "eigen.json").write_text(json.dumps(payload) + "\n")
    logger.info("eigen: {} tiles → {}", k + 1, out_dir / "eigen.webp")
    return result


def _tile(flat: np.ndarray) -> Image.Image:
    return Image.fromarray(flat.reshape(SIDE, SIDE, 3), mode="RGB")
