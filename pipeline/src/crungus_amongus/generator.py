"""Batch orchestration: work planning, retries, concurrency, manifest updates."""

import asyncio
import fnmatch
import time
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
from loguru import logger

from .config import IMAGES_PER_PROMPT, PROMPTS, Settings
from .exceptions import (
    NsfwBlockedError,
    PermanentPredictionError,
    RetryablePredictionError,
    SchemaIncompatibleError,
)
from .manifest import PERMANENT_STATUSES, ManifestEntry, append_entry, load_manifest
from .output_normalizer import output_urls, url_extension
from .registry import Registry, RegistryModel
from .replicate_client import ReplicateClient, download
from .schema_adapter import build_input


@dataclass(frozen=True)
class WorkItem:
    model: RegistryModel
    prompt_slug: str
    prompt: str
    image_index: int


@dataclass
class RunPolicy:
    concurrency: int = 4
    timeout_s: float = 300.0
    retries: int = 2
    retry_failed: bool = False
    max_predictions: int | None = None


def plan_work(
    registry: Registry,
    settings: Settings,
    model_pattern: str | None = None,
    prompt_filter: str | None = None,
    retry_failed: bool = False,
) -> list[WorkItem]:
    """Everything not yet in a permanent state, grouped by model."""
    manifest = load_manifest(settings.manifest_path)
    items: list[WorkItem] = []
    for model in registry.models:
        if model.availability != "ok" or model.version_id is None:
            continue
        if model_pattern and not (
            fnmatch.fnmatch(model.ref, model_pattern)
            or fnmatch.fnmatch(model.slug, model_pattern)
        ):
            continue
        for prompt_slug, prompt in PROMPTS.items():
            if prompt_filter and prompt_slug != prompt_filter:
                continue
            for index in range(IMAGES_PER_PROMPT):
                key = (model.owner, model.name, model.version_id, prompt_slug, index)
                prior = manifest.get(key)
                if (
                    prior is not None
                    and prior.status in PERMANENT_STATUSES
                    and not (retry_failed and prior.status == "failed_permanent")
                ):
                    continue
                items.append(WorkItem(model, prompt_slug, prompt, index))
    return items


async def run_batch(
    items: list[WorkItem], settings: Settings, policy: RunPolicy
) -> dict[str, int]:
    """Run pending work model-by-model; within a model, bounded concurrency."""
    if policy.max_predictions is not None:
        items = items[: policy.max_predictions]

    counts: dict[str, int] = {}
    headers = {"Authorization": f"Bearer {settings.replicate_api_token}"}
    async with (
        httpx.AsyncClient(headers=headers, timeout=90.0) as http,
        # presigned output URLs (e.g. R2) reject requests carrying an
        # Authorization header, so downloads use a clean client
        httpx.AsyncClient(timeout=120.0, follow_redirects=True) as download_http,
    ):
        client = ReplicateClient(http)
        semaphore = asyncio.Semaphore(policy.concurrency)

        by_model: dict[str, list[WorkItem]] = {}
        for item in items:
            by_model.setdefault(item.model.ref, []).append(item)

        for ref, model_items in by_model.items():
            logger.info("{}: {} predictions to run", ref, len(model_items))
            # circuit breaker: probe with one concurrency-wave first — a hung
            # or dead model then costs one timeout wave, not the whole set.
            # Skipped items get no manifest row, so the next run retries them.
            probe, rest = (
                model_items[: policy.concurrency],
                model_items[policy.concurrency :],
            )
            results = await asyncio.gather(
                *(
                    _run_one(item, client, download_http, settings, policy, semaphore)
                    for item in probe
                )
            )
            if rest:
                if any(status == "succeeded" for status in results):
                    results += await asyncio.gather(
                        *(
                            _run_one(
                                item, client, download_http, settings, policy, semaphore
                            )
                            for item in rest
                        )
                    )
                else:
                    logger.warning(
                        "{}: probe wave all failed ({}); skipping {} remaining items",
                        ref,
                        results,
                        len(rest),
                    )
            for status in results:
                counts[status] = counts.get(status, 0) + 1
    return counts


async def _run_one(
    item: WorkItem,
    client: ReplicateClient,
    download_http: httpx.AsyncClient,
    settings: Settings,
    policy: RunPolicy,
    semaphore: asyncio.Semaphore,
) -> str:
    """The per-prediction exception boundary. Returns the terminal status."""
    model = item.model
    assert model.version_id is not None
    entry = ManifestEntry(
        owner=model.owner,
        name=model.name,
        version_id=model.version_id,
        prompt_slug=item.prompt_slug,
        image_index=item.image_index,
        status="failed_permanent",
        created_at=datetime.now(tz=UTC),
    )

    try:
        payload = build_input(model, item.prompt)
    except SchemaIncompatibleError as exc:
        entry.status = "schema_incompatible"
        entry.error = str(exc)
        append_entry(settings.manifest_path, entry)
        return entry.status

    async with semaphore:
        start = time.monotonic()
        for attempt in range(1 + policy.retries):
            if attempt:
                await asyncio.sleep(5.0 * 2**attempt)
            try:
                prediction = await client.run_prediction(
                    owner=model.owner,
                    name=model.name,
                    version_id=model.version_id,
                    is_official=model.is_official,
                    payload=payload,
                    timeout_s=policy.timeout_s,
                )
                urls = output_urls(model, prediction.get("output"))
                image_bytes = await download(download_http, urls[0])
                entry.output_path = _save_original(item, image_bytes, urls[0], settings)
                entry.status = "succeeded"
                entry.prediction_id = prediction.get("id")
                metrics = prediction.get("metrics") or {}
                entry.predict_time_s = metrics.get("predict_time")
                break
            except RetryablePredictionError as exc:
                entry.status = (
                    "timeout" if "timed out" in str(exc) else "failed_retryable"
                )
                entry.error = str(exc)
                logger.warning(
                    "{} [{} #{}] attempt {}: {}",
                    model.ref,
                    item.prompt_slug,
                    item.image_index,
                    attempt + 1,
                    exc,
                )
            except NsfwBlockedError as exc:
                entry.status = "nsfw_blocked"
                entry.error = str(exc)
                break
            except PermanentPredictionError as exc:
                entry.status = "failed_permanent"
                entry.error = str(exc)
                break
        entry.wall_time_s = round(time.monotonic() - start, 2)

    entry.completed_at = datetime.now(tz=UTC)
    append_entry(settings.manifest_path, entry)
    if entry.status == "succeeded":
        logger.info(
            "{} [{} #{}] ok in {:.0f}s",
            model.ref,
            item.prompt_slug,
            item.image_index,
            entry.wall_time_s or 0,
        )
    else:
        logger.warning(
            "{} [{} #{}] {}: {}",
            model.ref,
            item.prompt_slug,
            item.image_index,
            entry.status,
            (entry.error or "")[:160],
        )
    return entry.status


def _save_original(
    item: WorkItem, image_bytes: bytes, url: str, settings: Settings
) -> str:
    relative = (
        f"{item.model.slug}/{item.prompt_slug}/{item.image_index}{url_extension(url)}"
    )
    path = settings.originals_dir / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(image_bytes)
    return relative
