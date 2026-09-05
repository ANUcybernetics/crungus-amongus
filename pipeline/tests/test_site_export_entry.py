from datetime import UTC, datetime
from pathlib import Path

from crungus_amongus.config import Settings
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
