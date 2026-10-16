"""Archive images → textured meshes, through Meshy's image-to-3D API.

Unlike the other modalities this one has no fixed sample: which images get a
mesh is a curated choice (data/mesh-queue.toml), since Meshy reads a single
full-bodied creature well and a min-dalle goat face or a page of text badly.

A Meshy task is paid for when it is created, not when it is collected, so the
task id goes into the append-only state/meshes.jsonl the moment Meshy hands it
over. A run that dies or times out while polling leaves a `submitted` row,
and the next run resumes that task rather than creating, and paying for,
another. Meshy refunds a FAILED task, so a failure costs nothing but is still
not retried without --retry-failed: it is a fact about the image.
"""

import asyncio
import base64
import tomllib
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import httpx
from loguru import logger
from pydantic import BaseModel, field_validator

from .config import Settings
from .manifest import redact

MESHY_API_BASE = "https://api.meshy.ai/openapi/v1"

# Pinned rather than "latest", for the reason the Replicate versions are: the
# mesh is a function of the model as much as of the image. Every request
# parameter is recorded with its task, so a change here is visible per mesh.
TASK_PARAMS: dict[str, Any] = {
    "ai_model": "meshy-7.1",
    "should_texture": True,
    # metallic/roughness/normal maps make it read as a surface, not paint
    "enable_pbr": True,
    "texture_resolution": "2k",
    # Meshy 7 doesn't remesh by default and can return far more triangles
    # than a browser wants; 100k triangles compresses to a few MB
    "should_remesh": True,
    "topology": "triangle",
    "target_polycount": 100_000,
    "target_formats": ["glb"],
}
# per mesh at TASK_PARAMS, from Meshy's pricing page (2K-textured mesh)
ASSUMED_CREDITS = 30
# Meshy's limit on the image itself (before base64)
MAX_IMAGE_BYTES = 20 * 1024 * 1024
IMAGE_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp"}

POLL_INTERVAL_S = 5.0
TERMINAL_STATUSES = {"SUCCEEDED", "FAILED", "CANCELED"}

type MeshStatus = Literal["submitted", "succeeded", "failed"]


class MeshEntry(BaseModel):
    """One line of state/meshes.jsonl; the last line per image wins."""

    image: str  # "<model-slug>/<prompt-slug>/<index>", the corpus stem
    task_id: str
    status: MeshStatus
    created_at: datetime
    completed_at: datetime | None = None
    consumed_credits: int | None = None
    error: str | None = None
    params: dict[str, Any] | None = None  # the request, on `submitted` rows

    _redact_error = field_validator("error")(lambda cls, v: redact(v))


def append_mesh_entry(path: Path, entry: MeshEntry) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(entry.model_dump_json(exclude_none=True) + "\n")


def read_mesh_manifest(path: Path) -> Iterator[MeshEntry]:
    if not path.exists():
        return
    with path.open() as f:
        for line in f:
            if line := line.strip():
                yield MeshEntry.model_validate_json(line)


def load_mesh_manifest(path: Path) -> dict[str, MeshEntry]:
    """The latest entry per image."""
    return {entry.image: entry for entry in read_mesh_manifest(path)}


def mesh_original(settings: Settings, stem: str, task_id: str) -> Path:
    return settings.mesh_originals_dir / stem / f"{task_id}.glb"


def load_queue(settings: Settings) -> list[str]:
    """The curated image stems, validated against the originals on disk.

    Accepts the keys the site and API show ("…/<index>.avif") or bare stems.
    An unknown key is an error before anything is sent, not a skipped item.
    """
    path = settings.mesh_queue_path
    if not path.exists():
        return []
    keys = tomllib.loads(path.read_text()).get("images", [])
    stems = list(dict.fromkeys(k.removesuffix(".avif") for k in keys))
    missing = [s for s in stems if find_original(settings, s) is None]
    if missing:
        raise ValueError(f"{path.name}: no original image for {missing}")
    return stems


def find_original(settings: Settings, stem: str) -> Path | None:
    for suffix in IMAGE_MIME:
        path = settings.originals_dir / f"{stem}{suffix}"
        if path.exists():
            return path
    return None


@dataclass(frozen=True)
class MeshJob:
    stem: str
    original: Path
    task_id: str | None = None  # set when resuming a task already paid for


def plan_meshes(settings: Settings, retry_failed: bool = False) -> list[MeshJob]:
    """Queued images without a mesh, resuming any task still in flight."""
    latest = load_mesh_manifest(settings.mesh_manifest_path)
    jobs: list[MeshJob] = []
    for stem in load_queue(settings):
        prior = latest.get(stem)
        if prior is not None and (
            prior.status == "succeeded"
            or (prior.status == "failed" and not retry_failed)
        ):
            continue
        original = find_original(settings, stem)
        assert original is not None  # load_queue checked
        resume = prior.task_id if prior and prior.status == "submitted" else None
        jobs.append(MeshJob(stem, original, resume))
    return jobs


def task_payload(original: Path) -> dict[str, Any]:
    data = original.read_bytes()
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError(f"{original} is over Meshy's 20 MB limit")
    encoded = base64.b64encode(data).decode()
    return {
        "image_url": f"data:{IMAGE_MIME[original.suffix]};base64,{encoded}",
        **TASK_PARAMS,
    }


class MeshyClient:
    """The three calls a mesh needs: create, poll, download.

    Downloads go through the same client but without the API key: the asset
    URLs are presigned, and a presigned URL has no business seeing it.
    """

    def __init__(
        self, http: httpx.AsyncClient, api_key: str, poll_interval_s: float
    ) -> None:
        self._http = http
        self._auth = {"Authorization": f"Bearer {api_key}"}
        self._poll_interval_s = poll_interval_s

    async def create(self, payload: dict[str, Any]) -> str:
        response = await self._http.post(
            f"{MESHY_API_BASE}/image-to-3d", json=payload, headers=self._auth
        )
        response.raise_for_status()
        return response.json()["result"]

    async def wait(self, task_id: str) -> dict[str, Any]:
        last: tuple[str, int] | None = None
        while True:
            response = await self._http.get(
                f"{MESHY_API_BASE}/image-to-3d/{task_id}", headers=self._auth
            )
            response.raise_for_status()
            task = response.json()
            state = (task["status"], task.get("progress", 0))
            if state != last:
                logger.debug("meshy {}: {} {}%", task_id, *state)
                last = state
            if task["status"] in TERMINAL_STATUSES:
                return task
            await asyncio.sleep(self._poll_interval_s)

    async def download(self, url: str, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        partial = dest.with_suffix(".part")
        async with self._http.stream("GET", url) as response:
            response.raise_for_status()
            with partial.open("wb") as f:
                async for chunk in response.aiter_bytes():
                    f.write(chunk)
        partial.rename(dest)


async def run_meshes(
    jobs: list[MeshJob],
    settings: Settings,
    client: MeshyClient,
    *,
    concurrency: int,
    timeout_s: float,
) -> dict[str, int]:
    """Run each job to a terminal state, or leave it `submitted` to resume.

    Any other error (a 402 for want of credits, a dropped connection) is
    raised: rows already written say exactly which tasks exist, so the next
    run picks up where this one stopped without paying twice.
    """
    semaphore = asyncio.Semaphore(concurrency)
    counts: dict[str, int] = {}

    async def one(job: MeshJob) -> None:
        async with semaphore:
            status = await _run_one(job, settings, client, timeout_s)
        counts[status] = counts.get(status, 0) + 1

    async with asyncio.TaskGroup() as group:
        for job in jobs:
            group.create_task(one(job))
    return counts


async def _run_one(
    job: MeshJob, settings: Settings, client: MeshyClient, timeout_s: float
) -> str:
    path = settings.mesh_manifest_path
    task_id = job.task_id
    if task_id is None:
        task_id = await client.create(task_payload(job.original))
        append_mesh_entry(
            path,
            MeshEntry(
                image=job.stem,
                task_id=task_id,
                status="submitted",
                created_at=datetime.now(tz=UTC),
                params=TASK_PARAMS,
            ),
        )
        logger.info("{}: submitted meshy task {}", job.stem, task_id)
    else:
        logger.info("{}: resuming meshy task {}", job.stem, task_id)

    try:
        async with asyncio.timeout(timeout_s):
            task = await client.wait(task_id)
    except TimeoutError:
        logger.warning(
            "{}: task {} unfinished after {:.0f}s; the next run resumes it",
            job.stem,
            task_id,
            timeout_s,
        )
        return "pending"

    completed_at = datetime.now(tz=UTC)
    if task["status"] != "SUCCEEDED":
        error = (task.get("task_error") or {}).get("message") or task["status"]
        append_mesh_entry(
            path,
            MeshEntry(
                image=job.stem,
                task_id=task_id,
                status="failed",
                created_at=completed_at,
                completed_at=completed_at,
                consumed_credits=task.get("consumed_credits"),
                error=error,
            ),
        )
        logger.warning("{}: meshy task {} failed: {}", job.stem, task_id, error)
        return "failed"

    await client.download(
        task["model_urls"]["glb"], mesh_original(settings, job.stem, task_id)
    )
    append_mesh_entry(
        path,
        MeshEntry(
            image=job.stem,
            task_id=task_id,
            status="succeeded",
            created_at=completed_at,
            completed_at=completed_at,
            consumed_credits=task.get("consumed_credits"),
        ),
    )
    logger.info(
        "{}: mesh ready ({} credits)", job.stem, task.get("consumed_credits", "?")
    )
    return "succeeded"
