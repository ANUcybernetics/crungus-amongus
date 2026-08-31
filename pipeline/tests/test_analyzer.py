import numpy as np
from crungus_amongus.analyzer import atlas_coords, consistency_scores


def unit(v: list[float]) -> np.ndarray:
    a = np.array(v, dtype=np.float32)
    return a / np.linalg.norm(a)


def test_identical_embeddings_score_one() -> None:
    e = unit([1.0, 0.0, 0.0])
    embeddings = {f"m/p/{i}": e for i in range(10)}
    scores = consistency_scores(embeddings)
    assert scores["m/p"] == 1.0


def test_orthogonal_embeddings_score_zero() -> None:
    embeddings = {
        "m/p/0": unit([1.0, 0.0]),
        "m/p/1": unit([0.0, 1.0]),
    }
    assert consistency_scores(embeddings)["m/p"] == 0.0


def test_groups_are_scored_independently_and_singletons_skipped() -> None:
    embeddings = {
        "a/p/0": unit([1.0, 0.0]),
        "a/p/1": unit([1.0, 0.0]),
        "b/p/0": unit([0.0, 1.0]),
    }
    scores = consistency_scores(embeddings)
    assert scores == {"a/p": 1.0}


def test_atlas_coords_normalised_to_unit_square() -> None:
    rng = np.random.default_rng(0)
    embeddings = {f"m/p/{i}": unit(list(rng.normal(size=8))) for i in range(30)}
    coords = atlas_coords(embeddings)
    assert set(coords) == set(embeddings)
    xs = [x for x, _ in coords.values()]
    ys = [y for _, y in coords.values()]
    assert min(xs) >= 0 and max(xs) <= 1
    assert min(ys) >= 0 and max(ys) <= 1
