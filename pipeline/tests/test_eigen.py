import numpy as np

from crungus_amongus.eigen import (
    dequantise,
    pca,
    quantise,
    stability,
    supervised_direction,
)


def test_components_are_orthonormal_and_ordered() -> None:
    rng = np.random.default_rng(0)
    rows = rng.normal(size=(40, 300)).astype(np.float32)
    result = pca(rows, 5)
    gram = result.components @ result.components.T
    assert np.allclose(gram, np.eye(5), atol=1e-4)
    assert np.all(np.diff(result.variance_ratio) <= 0)
    assert 0 < result.variance_ratio.sum() <= 1


def test_low_rank_data_is_reconstructed_exactly() -> None:
    rng = np.random.default_rng(1)
    basis = rng.normal(size=(3, 200)).astype(np.float32)
    weights = rng.normal(size=(50, 3)).astype(np.float32)
    rows = weights @ basis + 0.5
    result = pca(rows, 3)
    rebuilt = result.mean + result.coefficients @ result.components
    assert np.allclose(rebuilt, rows, atol=1e-3)
    assert np.isclose(result.variance_ratio.sum(), 1.0, atol=1e-4)


def test_extreme_image_projects_positively() -> None:
    rng = np.random.default_rng(2)
    rows = rng.normal(size=(30, 50)).astype(np.float32)
    result = pca(rows, 4)
    for j in range(4):
        extreme = np.argmax(np.abs(result.coefficients[:, j]))
        assert result.coefficients[extreme, j] > 0


def test_quantise_roundtrip_within_one_step() -> None:
    rng = np.random.default_rng(3)
    v = rng.normal(size=1000).astype(np.float32)
    q, scale = quantise(v)
    assert q.dtype == np.uint8
    assert np.abs(dequantise(q, scale) - v).max() <= scale / 127 / 2 + 1e-6


def test_stability_separates_a_planted_spectrum_from_its_degenerate_tail() -> None:
    """Well-gapped planted directions reproduce; a flat tail rotates freely."""
    rng = np.random.default_rng(7)
    d = 60
    basis = np.linalg.qr(rng.normal(size=(d, d)))[0]
    spectrum = np.array([40.0, 12.0, 4.0] + [1.0] * (d - 3))
    rows = ((rng.normal(size=(500, d)) * np.sqrt(spectrum)) @ basis.T).astype(
        np.float32
    )
    scores = stability(rows, 8, splits=4)
    assert scores[:3].min() > 0.9
    assert scores[3:].max() < 0.6


def test_stability_is_deterministic() -> None:
    rng = np.random.default_rng(8)
    rows = rng.normal(size=(80, 30)).astype(np.float32)
    assert np.array_equal(stability(rows, 4, splits=2), stability(rows, 4, splits=2))


def test_supervised_direction_recovers_a_planted_slope() -> None:
    rng = np.random.default_rng(9)
    slope = rng.normal(size=40).astype(np.float32)
    score = rng.normal(size=300).astype(np.float32)
    z = (score - score.mean()) / score.std()
    rows = (z[:, None] * slope + rng.normal(size=(300, 40)) * 0.01).astype(np.float32)
    direction, coefficients = supervised_direction(rows, score)
    assert np.allclose(direction, slope, atol=0.02)
    assert np.allclose(coefficients, z, atol=1e-5)


def test_supervised_axis_survives_resampling_by_construction() -> None:
    """The axis is the text embedding, so a resample cannot rotate it: images
    keep both their order and their spacing along it."""
    rng = np.random.default_rng(10)
    rows = rng.normal(size=(200, 40)).astype(np.float32)
    score = rng.normal(size=200).astype(np.float32)
    _, full = supervised_direction(rows, score)
    half = rng.permutation(200)[:100]
    _, resampled = supervised_direction(rows[half], score[half])
    assert np.array_equal(np.argsort(full[half]), np.argsort(resampled))
    # standardising against a different sample is an affine change of units,
    # so the ratio of any two gaps is identical
    gaps_full = np.diff(np.sort(full[half]))
    gaps_resampled = np.diff(np.sort(resampled))
    assert np.allclose(
        gaps_full / gaps_full.sum(), gaps_resampled / gaps_resampled.sum(), atol=1e-5
    )
