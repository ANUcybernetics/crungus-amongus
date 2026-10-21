from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from crungus_amongus.config import SAFETY_DEFAULTS_UNTIL, Modality, Settings
from crungus_amongus.manifest import ManifestEntry, Status, append_entry
from crungus_amongus.registry import Registry, RegistryModel
from crungus_amongus.site_export import SiteData, build_site_data, export_site_data


def make_settings(tmp_path: Path) -> Settings:
    return Settings(
        replicate_api_token="test-token",
        data_dir=tmp_path / "data",
        state_dir=tmp_path / "state",
    )


@pytest.mark.parametrize("modality", ["image", "audio", "video"])
def test_publish_reads_current_curated_descriptions(
    tmp_path: Path, modality: Modality
) -> None:
    settings = make_settings(tmp_path)
    settings.data_dir.mkdir()
    curated_path = settings.curated_models_path(modality)
    curated_path.write_text(
        '[[models]]\nowner = "example"\nname = "curated"\n'
        'description = "An image or audio model described for archive visitors."\n'
        'notes = "Internal pipeline details."\n'
        '\n[[models]]\nowner = "example"\nname = "fallback"\n'
        'notes = "Internal notes are not a description."\n'
    )
    registry = Registry(
        fetched_at=datetime.now(tz=UTC),
        models=[
            RegistryModel(
                owner="example",
                name=name,
                slug=f"example--{name}",
                source="collection",
                modality=modality,
                description="Original Replicate listing.",
                version_id="pinned-version",
            )
            for name in ("curated", "fallback")
        ],
    )
    original = registry.model_dump_json()
    out = tmp_path / "models.json"
    export_site_data(registry, settings, out)
    entries = {
        model.name: model
        for model in SiteData.model_validate_json(out.read_text()).models
    }
    assert entries["curated"].description == (
        "An image or audio model described for archive visitors."
    )
    assert entries["fallback"].description == "Original Replicate listing."
    assert entries["curated"].version_id == "pinned-version"
    assert registry.model_dump_json() == original

    # A copy edit takes effect without rediscovering or modifying the registry.
    curated_path.write_text(
        curated_path.read_text().replace(
            "An image or audio model described for archive visitors.",
            "Revised visitor-facing description.",
        )
    )
    entries = {
        model.name: model for model in build_site_data(registry, settings).models
    }
    assert entries["curated"].description == "Revised visitor-facing description."
    assert registry.model_dump_json() == original


def test_audio_model_publishes_clips_with_both_encodes(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    clip_dir = settings.optimized_dir / "meta--musicgen" / "crungus"
    clip_dir.mkdir(parents=True)
    (clip_dir / "0.opus").write_bytes(b"")
    (clip_dir / "0.m4a").write_bytes(b"")
    (clip_dir / "1.opus").write_bytes(b"")  # m4a missing: not published
    registry = Registry(
        fetched_at=datetime.now(tz=UTC),
        models=[
            RegistryModel(
                owner="meta",
                name="musicgen",
                slug="meta--musicgen",
                source="collection",
                modality="audio",
                version_id="v1",
            )
        ],
    )

    entry = build_site_data(registry, settings).models[0]
    assert entry.modality == "audio"
    assert entry.status == "partial"
    assert [p.prompt_slug for p in entry.prompts] == [
        "crungus",
        "the-sound-of-a-crungus",
    ]
    clips = entry.prompts[0].clips
    assert [c.opus for c in clips] == ["meta--musicgen/crungus/0.opus"]
    assert [c.m4a for c in clips] == ["meta--musicgen/crungus/0.m4a"]
    assert entry.prompts[0].images == []


def test_video_model_publishes_clips_with_their_posters(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    clip_dir = settings.optimized_dir / "google--veo-3" / "crungus"
    clip_dir.mkdir(parents=True)
    for name in ("0.av1.mp4", "0.mp4", "0.jpg", "1.mp4", "1.jpg"):
        (clip_dir / name).write_bytes(b"")  # 1 has no AV1 encode: not published
    registry = Registry(
        fetched_at=datetime.now(tz=UTC),
        models=[
            RegistryModel(
                owner="google",
                name="veo-3",
                slug="google--veo-3",
                source="collection",
                modality="video",
                version_id="v1",
            )
        ],
    )

    entry = build_site_data(registry, settings).models[0]
    assert entry.status == "partial"
    assert [p.prompt_slug for p in entry.prompts] == ["crungus", "a-video-of-a-crungus"]
    videos = entry.prompts[0].videos
    stem = "google--veo-3/crungus/0"
    assert [(v.av1, v.mp4, v.poster) for v in videos] == [
        (f"{stem}.av1.mp4", f"{stem}.mp4", f"{stem}.jpg")
    ]
    assert entry.prompts[0].images == entry.prompts[0].clips == []


def test_attempts_publish_the_refusals_not_just_the_survivors(tmp_path: Path) -> None:
    """A model that will not draw a crungus is a finding, so the count ships."""
    settings = make_settings(tmp_path)
    image_dir = settings.optimized_dir / "bfl--flux" / "crungus"
    image_dir.mkdir(parents=True)
    (image_dir / "0.avif").write_bytes(b"")
    statuses: list[Status] = [
        "succeeded",
        "nsfw_blocked",
        "nsfw_blocked",
        "failed_permanent",
    ]
    for index, status in enumerate(statuses):
        append_entry(
            settings.manifest_path,
            ManifestEntry(
                owner="bfl",
                name="flux",
                version_id="v1",
                prompt_slug="crungus",
                image_index=index,
                status=status,
                created_at=datetime.now(tz=UTC),
            ),
        )
    # an older pin's rows must not be counted against the current one
    append_entry(
        settings.manifest_path,
        ManifestEntry(
            owner="bfl",
            name="flux",
            version_id="v0",
            prompt_slug="crungus",
            image_index=0,
            status="nsfw_blocked",
            created_at=datetime.now(tz=UTC),
        ),
    )

    entry = build_site_data(_image_registry(), settings).models[0]
    attempts = entry.prompts[0].attempts
    assert (attempts.total, attempts.succeeded, attempts.refused, attempts.failed) == (
        4,
        1,
        2,
        1,
    )
    # the untouched prompt has been asked nothing at all
    assert entry.prompts[1].attempts.total == 0


def _image_registry() -> Registry:
    return Registry(
        fetched_at=datetime.now(tz=UTC),
        models=[
            RegistryModel(
                owner="bfl",
                name="flux",
                slug="bfl--flux",
                source="collection",
                modality="image",
                version_id="v1",
            )
        ],
    )


def test_refusals_are_a_frozen_pre_cutover_measurement(tmp_path: Path) -> None:
    """A refusal later re-rolled into a success still happened; a refusal after
    the filters came off is not part of the record at all."""
    settings = make_settings(tmp_path)
    image_dir = settings.optimized_dir / "bfl--flux" / "crungus"
    image_dir.mkdir(parents=True)
    (image_dir / "0.avif").write_bytes(b"")

    before = SAFETY_DEFAULTS_UNTIL - timedelta(days=1)
    after = SAFETY_DEFAULTS_UNTIL + timedelta(days=1)

    def row(index: int, status: Status, when: datetime) -> None:
        append_entry(
            settings.manifest_path,
            ManifestEntry(
                owner="bfl",
                name="flux",
                version_id="v1",
                prompt_slug="crungus",
                image_index=index,
                status=status,
                created_at=when,
            ),
        )

    row(0, "nsfw_blocked", before)
    row(0, "succeeded", before)  # re-rolled, but the refusal is still recorded
    row(1, "succeeded", before)
    row(2, "nsfw_blocked", after)  # filters off by now: outside the measurement

    prompt = build_site_data(_image_registry(), settings).models[0].prompts[0]
    assert (prompt.refusals.asked, prompt.refusals.refused) == (3, 1)
    assert prompt.refusals.measured_until == SAFETY_DEFAULTS_UNTIL
    # the corpus view is last-wins, so slot 0 counts once, as a success
    assert prompt.attempts.succeeded == 2
