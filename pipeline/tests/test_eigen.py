import numpy as np

from crungus_amongus.eigen import (
    Pca,
    dequantise,
    pca,
    quantise,
    stability,
    supervised_direction,
)


def gram_pca(rows: np.ndarray, k: int) -> Pca:
    """The exact Turk & Pentland decomposition that `pca` replaced.

    Kept here as the reference the randomised SVD is pinned against: it is
    unusable at corpus scale (a centred copy plus an N x N Gram matrix), but at
    test size it is the ground truth.
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
    return Pca(
        mean=mean,
        components=components,
        coefficients=coefficients,
        variance_ratio=(eigenvalues / float(np.trace(gram))).astype(np.float32),
    )


def assert_matches_gram(rows: np.ndarray, k: int) -> None:
    reference = gram_pca(rows, k)
    result = pca(rows, k)
    # the sign convention is part of the contract, so these should agree
    # outright rather than only up to sign
    aligned = np.sum(result.components * reference.components, axis=1)
    assert np.all(aligned > 0)
    assert np.abs(np.abs(aligned) - 1).max() < 1e-4
    assert np.abs(result.variance_ratio - reference.variance_ratio).max() < 1e-6
    assert np.allclose(result.mean, reference.mean, atol=1e-6)


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


def test_randomised_svd_matches_the_gram_decomposition_on_a_spectrum() -> None:
    """The regime the archive is in: singular values that decay, so the top
    components are identified and both implementations must find the same ones."""
    rng = np.random.default_rng(11)
    basis = np.linalg.qr(rng.normal(size=(800, 800)))[0]
    decay = rng.normal(size=(300, 800)) * 0.85 ** np.arange(800)
    assert_matches_gram((decay @ basis.T).astype(np.float32), 24)


def test_randomised_svd_matches_the_gram_decomposition_on_a_full_sketch() -> None:
    """When the sketch is as wide as the centred matrix's rank it spans the
    whole range, so agreement holds even on a flat spectrum with no gaps."""
    rng = np.random.default_rng(12)
    assert_matches_gram(rng.normal(size=(40, 300)).astype(np.float32), 5)


def test_variance_ratios_sum_over_a_block_boundary() -> None:
    """Total variance is accumulated a block at a time; the blocking must not
    show up in the answer."""
    rng = np.random.default_rng(13)
    rows = rng.normal(size=(2500, 40)).astype(np.float32)  # more rows than a block
    result = pca(rows, 40)  # every component, so the shares must sum to one
    assert np.isclose(result.variance_ratio.sum(), 1.0, atol=1e-4)


def test_stability_scores_zero_where_a_half_cannot_reach() -> None:
    """A half of a small archive has fewer components than the whole does, and
    the ones it cannot offer are unmeasurable rather than an index error."""
    rng = np.random.default_rng(14)
    rows = rng.normal(size=(8, 60)).astype(np.float32)
    scores = stability(rows, 7, splits=2)
    assert scores.shape == (7,)
    # four rows per half span three directions; the rest score zero
    assert np.all(scores[:3] > 0)
    assert np.array_equal(scores[3:], np.zeros(4, dtype=np.float32))
