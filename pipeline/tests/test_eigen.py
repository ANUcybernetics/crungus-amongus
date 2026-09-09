import numpy as np

from crungus_amongus.eigen import dequantise, pca, quantise


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
