from datetime import UTC, datetime
from typing import Any

from crungus_amongus.registry import (
    CuratedModel,
    DenyEntry,
    Registry,
    build_registry,
    slugify,
)


def collection_payload(owner: str, name: str, version_id: str = "v1") -> dict[str, Any]:
    return {
        "owner": owner,
        "name": name,
        "description": f"{name} description",
        "latest_version": {
            "id": version_id,
            "created_at": "2024-01-01T00:00:00Z",
            "openapi_schema": {
                "components": {
                    "schemas": {"Input": {"properties": {"prompt": {"type": "string"}}}}
                }
            },
        },
    }


def no_legacy(owner: str, name: str) -> dict[str, Any] | None:
    raise AssertionError(f"unexpected legacy fetch: {owner}/{name}")


def test_collection_and_legacy_merge_with_overrides() -> None:
    collection = [collection_payload("stability-ai", "sdxl")]
    curated = [
        CuratedModel(owner="stability-ai", name="sdxl", notes="override only"),
        CuratedModel(owner="kuprel", name="min-dalle", prompt_field="text"),
    ]

    registry = build_registry(
        collection_payloads=collection,
        curated=curated,
        deny=[],
        existing=None,
        fetch_legacy=lambda o, n: collection_payload(o, n, version_id="legacy-v"),
    )

    by_ref = registry.by_ref()
    assert set(by_ref) == {"stability-ai/sdxl", "kuprel/min-dalle"}
    sdxl = by_ref["stability-ai/sdxl"]
    assert sdxl.source == "collection"
    assert sdxl.notes == "override only"  # curated entry overrides, no duplicate
    mindalle = by_ref["kuprel/min-dalle"]
    assert mindalle.source == "legacy"
    assert mindalle.prompt_field == "text"
    assert mindalle.version_id == "legacy-v"


def test_deny_list_removes_models() -> None:
    registry = build_registry(
        collection_payloads=[collection_payload("a", "b")],
        curated=[],
        deny=[DenyEntry(owner="a", name="b", reason="img2img only")],
        existing=None,
        fetch_legacy=no_legacy,
    )
    assert registry.models == []


def test_version_pinning_is_sticky() -> None:
    first = build_registry(
        collection_payloads=[collection_payload("a", "b", version_id="old")],
        curated=[],
        deny=[],
        existing=None,
        fetch_legacy=no_legacy,
    )
    second = build_registry(
        collection_payloads=[collection_payload("a", "b", version_id="new")],
        curated=[],
        deny=[],
        existing=first,
        fetch_legacy=no_legacy,
    )
    assert second.models[0].version_id == "old"

    refreshed = build_registry(
        collection_payloads=[collection_payload("a", "b", version_id="new")],
        curated=[],
        deny=[],
        existing=first,
        fetch_legacy=no_legacy,
        refresh_versions=True,
    )
    assert refreshed.models[0].version_id == "new"


def test_missing_legacy_model_marked_unavailable() -> None:
    registry = build_registry(
        collection_payloads=[],
        curated=[CuratedModel(owner="gone", name="model")],
        deny=[],
        existing=None,
        fetch_legacy=lambda o, n: None,
    )
    entry = registry.models[0]
    assert entry.availability == "unavailable"
    assert entry.version_id is None


def test_unavailable_legacy_model_keeps_prior_pin() -> None:
    prior = Registry(
        fetched_at=datetime.now(tz=UTC),
        models=build_registry(
            collection_payloads=[],
            curated=[CuratedModel(owner="gone", name="model")],
            deny=[],
            existing=None,
            fetch_legacy=lambda o, n: collection_payload(o, n, version_id="pinned"),
        ).models,
    )
    registry = build_registry(
        collection_payloads=[],
        curated=[CuratedModel(owner="gone", name="model")],
        deny=[],
        existing=prior,
        fetch_legacy=lambda o, n: None,
    )
    entry = registry.models[0]
    assert entry.version_id == "pinned"
    assert entry.availability == "ok"


def test_slugify() -> None:
    assert slugify("stability-ai", "sdxl") == "stability-ai--sdxl"
    assert slugify("cjwbw", "anything-v3.0") == "cjwbw--anything-v3-0"
