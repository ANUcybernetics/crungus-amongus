"""Model registry: Replicate's text-to-image collection merged with the curated list.

The registry (state/models.json) pins each model to a version id. Pinning is
sticky: re-running discover never bumps an existing pin (that would orphan
generated images and imply re-spend) unless --refresh-versions is passed.
"""

import tomllib
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Literal

import httpx
from loguru import logger
from pydantic import BaseModel, Field

from .config import COLLECTION_SLUG, REPLICATE_API_BASE


class CuratedModel(BaseModel):
    """An entry in data/curated-models.toml.

    Also the override mechanism for collection models: an entry whose
    (owner, name) matches a collection model contributes its overrides
    rather than adding a duplicate.
    """

    owner: str
    name: str
    prompt_field: str | None = None
    extra_inputs: dict[str, Any] = Field(default_factory=dict)
    output_field: str | None = None
    release_date: date | None = None
    notes: str | None = None


class DenyEntry(BaseModel):
    owner: str
    name: str
    reason: str


class RegistryModel(BaseModel):
    owner: str
    name: str
    slug: str
    source: Literal["collection", "legacy"]
    description: str | None = None
    # official models are routed by Replicate: predictions must use the
    # model-scoped endpoint and version pinning does not apply
    is_official: bool = False
    availability: Literal["ok", "unavailable"] = "ok"
    version_id: str | None = None
    version_created_at: datetime | None = None
    input_schema: dict[str, Any] | None = None
    # curated overrides, merged in
    prompt_field: str | None = None
    extra_inputs: dict[str, Any] = Field(default_factory=dict)
    output_field: str | None = None
    release_date: date | None = None
    notes: str | None = None

    @property
    def ref(self) -> str:
        return f"{self.owner}/{self.name}"


class Registry(BaseModel):
    fetched_at: datetime
    models: list[RegistryModel]

    def by_ref(self) -> dict[str, RegistryModel]:
        return {m.ref: m for m in self.models}


def slugify(owner: str, name: str) -> str:
    raw = f"{owner}--{name}".lower()
    return "".join(c if c.isalnum() or c == "-" else "-" for c in raw)


def load_curated(path: Path) -> list[CuratedModel]:
    doc = tomllib.loads(path.read_text())
    return [CuratedModel.model_validate(entry) for entry in doc.get("models", [])]


def load_deny_list(path: Path) -> list[DenyEntry]:
    if not path.exists():
        return []
    doc = tomllib.loads(path.read_text())
    return [DenyEntry.model_validate(entry) for entry in doc.get("models", [])]


def load_registry(path: Path) -> Registry | None:
    if not path.exists():
        return None
    return Registry.model_validate_json(path.read_text())


def save_registry(registry: Registry, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(registry.model_dump_json(indent=2) + "\n")


def _extract_input_schema(model_payload: dict[str, Any]) -> dict[str, Any] | None:
    version = model_payload.get("latest_version")
    if not version:
        return None
    schema = version.get("openapi_schema") or {}
    return schema.get("components", {}).get("schemas", {}).get("Input")


def _version_fields(
    model_payload: dict[str, Any],
) -> tuple[str | None, datetime | None, dict[str, Any] | None]:
    version = model_payload.get("latest_version")
    if not version:
        return None, None, None
    created = version.get("created_at")
    created_at = datetime.fromisoformat(created) if created else None
    return version.get("id"), created_at, _extract_input_schema(model_payload)


def fetch_collection_models(client: httpx.Client) -> list[dict[str, Any]]:
    """Fetch every model object in the text-to-image collection, following pagination."""
    models: list[dict[str, Any]] = []
    url: str | None = f"{REPLICATE_API_BASE}/collections/{COLLECTION_SLUG}"
    while url:
        response = client.get(url)
        response.raise_for_status()
        payload = response.json()
        models.extend(payload.get("models", []))
        url = payload.get("next")
    return models


def fetch_model(client: httpx.Client, owner: str, name: str) -> dict[str, Any] | None:
    """Fetch a single model, returning None when it no longer exists."""
    response = client.get(f"{REPLICATE_API_BASE}/models/{owner}/{name}")
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()


type LegacyFetcher = Callable[[str, str], dict[str, Any] | None]


def build_registry(
    collection_payloads: list[dict[str, Any]],
    curated: list[CuratedModel],
    deny: list[DenyEntry],
    existing: Registry | None,
    fetch_legacy: LegacyFetcher,
    refresh_versions: bool = False,
) -> Registry:
    """Merge the collection, the curated list, and the existing registry.

    Pure with respect to the collection payloads; legacy models not present in
    the collection are fetched via fetch_legacy (injected for testability).
    """
    denied = {(d.owner, d.name) for d in deny}
    curated_by_ref = {(c.owner, c.name): c for c in curated}
    existing_by_ref = existing.by_ref() if existing else {}

    models: list[RegistryModel] = []
    seen: set[tuple[str, str]] = set()

    for payload in collection_payloads:
        owner, name = payload["owner"], payload["name"]
        if (owner, name) in denied or (owner, name) in seen:
            continue
        seen.add((owner, name))
        models.append(
            _make_entry(
                payload,
                "collection",
                curated_by_ref.get((owner, name)),
                existing_by_ref.get(f"{owner}/{name}"),
                refresh_versions,
            )
        )

    for c in curated:
        if (c.owner, c.name) in denied or (c.owner, c.name) in seen:
            continue
        seen.add((c.owner, c.name))
        payload = fetch_legacy(c.owner, c.name)
        if payload is None:
            prior = existing_by_ref.get(f"{c.owner}/{c.name}")
            logger.warning("legacy model {}/{} not found on Replicate", c.owner, c.name)
            entry = _make_entry(
                {"owner": c.owner, "name": c.name}, "legacy", c, prior, refresh_versions
            )
            entry.availability = (
                "unavailable" if entry.version_id is None else entry.availability
            )
            models.append(entry)
        else:
            models.append(
                _make_entry(
                    payload,
                    "legacy",
                    c,
                    existing_by_ref.get(f"{c.owner}/{c.name}"),
                    refresh_versions,
                )
            )

    return Registry(fetched_at=datetime.now(tz=UTC), models=models)


def _make_entry(
    payload: dict[str, Any],
    source: Literal["collection", "legacy"],
    override: CuratedModel | None,
    prior: RegistryModel | None,
    refresh_versions: bool,
) -> RegistryModel:
    owner, name = payload["owner"], payload["name"]
    version_id, version_created_at, input_schema = _version_fields(payload)

    # sticky pinning: an existing pin survives unless explicitly refreshed
    if prior is not None and prior.version_id is not None and not refresh_versions:
        version_id = prior.version_id
        version_created_at = prior.version_created_at
        input_schema = prior.input_schema

    return RegistryModel(
        owner=owner,
        name=name,
        slug=slugify(owner, name),
        source=source,
        description=payload.get("description"),
        is_official=bool(payload.get("is_official", False)),
        availability="ok" if version_id else "unavailable",
        version_id=version_id,
        version_created_at=version_created_at,
        input_schema=input_schema,
        prompt_field=override.prompt_field if override else None,
        extra_inputs=dict(override.extra_inputs) if override else {},
        output_field=override.output_field if override else None,
        release_date=override.release_date if override else None,
        notes=override.notes if override else None,
    )
