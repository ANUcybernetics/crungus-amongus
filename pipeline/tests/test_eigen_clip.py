import json

import numpy as np
import pytest
from PIL import Image

from crungus_amongus.analyzer import (
    ATLAS_CLIP,
    SEMANTIC_CLIP,
    cache_path,
    save_embeddings,
    unit_rows,
)
from crungus_amongus.bucket_sync import (
    CACHE_CONTROL,
    MUTABLE_CACHE_CONTROL,
    upload_plan,
)
from crungus_amongus.config import Settings
from crungus_amongus.eigen import build_eigen
from crungus_amongus.eigen_clip import (
    FILMSTRIP_STEPS,
    MEAN_FRAME,
    SIGMA_SPAN,
    component_dir,
    corpus_rows,
    frame_for_sigma,
    frame_keys,
    frame_offsets,
)
from crungus_amongus.sprite import build_sprite


def corpus(settings: Settings, count: int = 8) -> list[str]:
    """A small optimized tree, and the keys it should present."""
    rng = np.random.default_rng(0)
    keys = []
    for i in range(count):
        directory = settings.optimized_dir / f"owner--m{i % 2}" / "crungus"
        directory.mkdir(parents=True, exist_ok=True)
        pixels = rng.integers(0, 255, size=(16, 16, 3), dtype=np.uint8)
        Image.fromarray(pixels).save(directory / f"{i}.avif", format="AVIF")
        keys.append(f"owner--m{i % 2}/crungus/{i}.avif")
    return sorted(keys)


def test_the_filmstrip_spans_plus_and_minus_three_sigma_around_the_mean() -> None:
    offsets = frame_offsets()
    assert len(offsets) == FILMSTRIP_STEPS
    assert offsets[0] == -SIGMA_SPAN and offsets[-1] == SIGMA_SPAN
    # odd number of frames, so the centre frame is the mean crungus exactly
    assert offsets[FILMSTRIP_STEPS // 2] == 0.0


def test_frame_index_is_monotone_and_clamped_to_the_strip() -> None:
    positions = np.linspace(-2 * SIGMA_SPAN, 2 * SIGMA_SPAN, 401)
    indices = [frame_for_sigma(float(p)) for p in positions]
    assert indices == sorted(indices)
    assert min(indices) == 0 and max(indices) == FILMSTRIP_STEPS - 1
    # a slider dragged past the rendered range holds on the end frame
    assert frame_for_sigma(-99.0) == 0
    assert frame_for_sigma(99.0) == FILMSTRIP_STEPS - 1


def test_each_offset_maps_back_to_its_own_frame() -> None:
    """The index maths and the rendered offsets are the same convention."""
    assert [frame_for_sigma(float(o)) for o in frame_offsets()] == list(
        range(FILMSTRIP_STEPS)
    )


def test_every_axis_shares_the_centre_frame() -> None:
    """The mean crungus sits at 0σ on every axis, so it is rendered once."""
    keys = frame_keys(component_dir(1))
    assert len(keys) == FILMSTRIP_STEPS
    assert keys[FILMSTRIP_STEPS // 2] == f"eigen-clip/{MEAN_FRAME}"
    assert keys[FILMSTRIP_STEPS // 2] == frame_keys("text")[FILMSTRIP_STEPS // 2]
    assert keys[0] == "eigen-clip/c01/0.avif"


def test_corpus_rows_follow_the_optimized_tree_not_the_cache(tmp_path) -> None:
    settings = Settings(replicate_api_token="x", data_dir=tmp_path)
    keys = corpus(settings)
    rng = np.random.default_rng(1)
    embeddings = {
        key.removesuffix(".avif"): rng.normal(size=4).astype(np.float32) for key in keys
    }
    embeddings["owner--gone/crungus/0"] = np.zeros(4, dtype=np.float32)

    ordered, rows = corpus_rows(settings, embeddings)

    assert ordered == keys  # a stale cache entry cannot join the decomposition
    assert rows.shape == (len(keys), 4)
    for i, key in enumerate(ordered):
        assert np.array_equal(rows[i], embeddings[key.removesuffix(".avif")])


def test_corpus_rows_refuse_a_partially_embedded_archive(tmp_path) -> None:
    settings = Settings(replicate_api_token="x", data_dir=tmp_path)
    keys = corpus(settings)
    embeddings = {
        key.removesuffix(".avif"): np.zeros(4, dtype=np.float32) for key in keys[:-1]
    }
    with pytest.raises(RuntimeError, match="no ViT-bigG-14 embedding"):
        corpus_rows(settings, embeddings)


def test_unit_rows_normalises_without_touching_direction() -> None:
    rows = np.array([[3.0, 4.0], [0.0, 2.0]], dtype=np.float32)
    unit = unit_rows(rows)
    assert np.allclose(np.linalg.norm(unit, axis=1), 1.0)
    assert np.allclose(unit[0], [0.6, 0.8])


def test_rendered_frames_are_invisible_to_the_corpus_they_came_from(tmp_path) -> None:
    """The whole reason data/derived/ exists.

    embed_images, build_sprite and build_eigen all walk the optimized tree, so
    a Kandinsky render stored there would silently join the archive it was
    derived from — feeding the atlas, the pixel eigencrungi and the consistency
    scores with the pipeline's own output.
    """
    settings = Settings(replicate_api_token="x", data_dir=tmp_path)
    keys = corpus(settings)
    intruder = settings.derived_dir / "eigen-clip" / "c01" / "0.avif"
    intruder.parent.mkdir(parents=True)
    Image.new("RGB", (16, 16), (255, 0, 255)).save(intruder, format="AVIF")
    assert not intruder.is_relative_to(settings.optimized_dir)

    # a full cache means embed_images short-circuits before loading any model:
    # what it returns is exactly what it considers to be the corpus
    cache = cache_path(settings, ATLAS_CLIP)
    save_embeddings(
        cache,
        {key.removesuffix(".avif"): np.zeros(4, dtype=np.float32) for key in keys},
    )
    from crungus_amongus.analyzer import embed_images

    assert sorted(embed_images(settings)) == [key.removesuffix(".avif") for key in keys]
    assert build_sprite(settings, tmp_path / "atlas") == keys

    # the corpus view is what is under test; take the cache away so build_eigen
    # skips the supervised axis rather than loading CLIP to embed a word
    cache.unlink()

    build_eigen(settings, tmp_path / "eigen")
    payload = json.loads((tmp_path / "eigen" / "eigen.json").read_text())
    assert sorted(payload["coefficients"]) == keys
    assert payload["image_count"] == len(keys)


def test_sync_ships_the_derived_tree_without_caching_it_forever(tmp_path) -> None:
    settings = Settings(replicate_api_token="x", data_dir=tmp_path)
    corpus(settings, count=1)
    frame = settings.derived_dir / "eigen-clip" / "c01" / "0.avif"
    frame.parent.mkdir(parents=True)
    Image.new("RGB", (8, 8)).save(frame, format="AVIF")

    plan = {item.key: item for item in upload_plan(settings)}

    assert plan["eigen-clip/c01/0.avif"].path == frame
    # a corpus key embeds its pinned model version, so it never changes; a
    # derived one is overwritten every time the corpus grows
    assert plan["owner--m0/crungus/0.avif"].cache == CACHE_CONTROL
    assert plan["eigen-clip/c01/0.avif"].cache == MUTABLE_CACHE_CONTROL


def test_the_semantic_cache_is_a_different_file_from_the_atlas_one(tmp_path) -> None:
    settings = Settings(replicate_api_token="x", data_dir=tmp_path)
    assert cache_path(settings, ATLAS_CLIP) != cache_path(settings, SEMANTIC_CLIP)
    # the decoder needs embeddings at their native scale, the scores do not
    assert ATLAS_CLIP.normalise and not SEMANTIC_CLIP.normalise
