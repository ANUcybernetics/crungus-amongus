from datetime import UTC, datetime
from pathlib import Path

from crungus_amongus.config import Settings
from crungus_amongus.manifest import ManifestEntry, append_entry
from crungus_amongus.registry import Registry, RegistryModel
from crungus_amongus.site_export import build_site_data


def make_settings(tmp_path: Path) -> Settings:
    return Settings(
        replicate_api_token="test-token",
        data_dir=tmp_path / "data",
        state_dir=tmp_path / "state",
    )


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


def test_attempts_publish_the_refusals_not_just_the_survivors(tmp_path: Path) -> None:
    """A model that will not draw a crungus is a finding, so the count ships."""
    settings = make_settings(tmp_path)
    image_dir = settings.optimized_dir / "bfl--flux" / "crungus"
    image_dir.mkdir(parents=True)
    (image_dir / "0.avif").write_bytes(b"")
    for index, status in enumerate(
        ["succeeded", "nsfw_blocked", "nsfw_blocked", "failed_permanent"]
    ):
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
