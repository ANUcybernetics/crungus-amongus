from datetime import UTC, datetime
from pathlib import Path

from crungus_amongus.config import OUTPUTS_PER_PROMPT, PROMPTS, Settings
from crungus_amongus.generator import plan_work
from crungus_amongus.manifest import ManifestEntry, Status, append_entry, load_manifest
from crungus_amongus.registry import Registry, RegistryModel


def make_settings(tmp_path: Path) -> Settings:
    return Settings(
        replicate_api_token="test-token",
        data_dir=tmp_path / "data",
        state_dir=tmp_path / "state",
    )


def make_registry() -> Registry:
    return Registry(
        fetched_at=datetime.now(tz=UTC),
        models=[
            RegistryModel(
                owner="a",
                name="b",
                slug="a--b",
                source="collection",
                version_id="v1",
                input_schema={"properties": {"prompt": {"type": "string"}}},
            )
        ],
    )


def entry(
    status: Status, index: int = 0, prompt_slug: str = "crungus"
) -> ManifestEntry:
    return ManifestEntry(
        owner="a",
        name="b",
        version_id="v1",
        prompt_slug=prompt_slug,
        image_index=index,
        status=status,
        created_at=datetime.now(tz=UTC),
    )


def test_manifest_last_entry_wins(tmp_path: Path) -> None:
    path = tmp_path / "manifest.jsonl"
    append_entry(path, entry("failed_retryable"))
    append_entry(path, entry("succeeded"))
    loaded = load_manifest(path)
    assert len(loaded) == 1
    assert next(iter(loaded.values())).status == "succeeded"


def test_plan_work_full_and_resume(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    registry = make_registry()

    total = len(PROMPTS["image"]) * OUTPUTS_PER_PROMPT["image"]
    assert len(plan_work(registry, settings)) == total

    # permanent states are skipped; retryable states are retried
    append_entry(settings.manifest_path, entry("succeeded", index=0))
    append_entry(settings.manifest_path, entry("nsfw_blocked", index=1))
    append_entry(settings.manifest_path, entry("failed_permanent", index=2))
    append_entry(settings.manifest_path, entry("timeout", index=3))
    append_entry(settings.manifest_path, entry("failed_retryable", index=4))

    remaining = plan_work(registry, settings)
    indices = {(i.prompt_slug, i.image_index) for i in remaining}
    assert ("crungus", 0) not in indices
    assert ("crungus", 1) not in indices
    assert ("crungus", 2) not in indices
    assert ("crungus", 3) in indices
    assert ("crungus", 4) in indices
    assert len(remaining) == total - 3

    # --retry-failed brings back failed_permanent but not succeeded/nsfw
    with_retry = plan_work(registry, settings, retry_failed=True)
    retry_indices = {(i.prompt_slug, i.image_index) for i in with_retry}
    assert ("crungus", 2) in retry_indices
    assert ("crungus", 0) not in retry_indices


def test_version_change_invalidates_prior_work(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    registry = make_registry()
    append_entry(settings.manifest_path, entry("succeeded", index=0))
    registry.models[0].version_id = "v2"
    total = len(PROMPTS["image"]) * OUTPUTS_PER_PROMPT["image"]
    assert len(plan_work(registry, settings)) == total


def test_plan_work_uses_the_modality_prompt_set(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    registry = make_registry()
    registry.models[0].modality = "audio"
    items = plan_work(registry, settings)
    assert {i.prompt_slug for i in items} == set(PROMPTS["audio"])
    assert len(items) == len(PROMPTS["audio"]) * OUTPUTS_PER_PROMPT["audio"]
    assert plan_work(registry, settings, modality="image") == []


def test_retry_failed_re_rolls_nsfw_blocks(tmp_path: Path) -> None:
    """An NSFW block judges the output, not the prompt, so a fresh seed may pass."""
    settings = make_settings(tmp_path)
    registry = make_registry()
    for index, status in (
        (0, "nsfw_blocked"),
        (1, "failed_permanent"),
        (2, "succeeded"),
    ):
        append_entry(settings.manifest_path, entry(status, index=index))

    without = {(i.prompt_slug, i.image_index) for i in plan_work(registry, settings)}
    assert ("crungus", 0) not in without
    assert ("crungus", 1) not in without

    with_retry = {
        (i.prompt_slug, i.image_index)
        for i in plan_work(registry, settings, retry_failed=True)
    }
    assert ("crungus", 0) in with_retry  # the NSFW block is re-rolled
    assert ("crungus", 1) in with_retry
    assert ("crungus", 2) not in with_retry  # a success is never re-spent


def test_retry_failed_leaves_schema_incompatible_alone(tmp_path: Path) -> None:
    """A missing prompt field never resolves itself; re-rolling it only spends."""
    settings = make_settings(tmp_path)
    registry = make_registry()
    append_entry(settings.manifest_path, entry("schema_incompatible"))
    planned = {
        (i.prompt_slug, i.image_index)
        for i in plan_work(registry, settings, retry_failed=True)
    }
    assert ("crungus", 0) not in planned
