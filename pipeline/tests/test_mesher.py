import asyncio
import json
import struct
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from PIL import Image

from crungus_amongus.bucket_sync import CACHE_CONTROL, upload_plan
from crungus_amongus.config import Settings
from crungus_amongus.mesher import (
    MeshEntry,
    MeshyClient,
    append_mesh_entry,
    load_mesh_manifest,
    load_queue,
    mesh_original,
    plan_meshes,
    run_meshes,
)
from crungus_amongus.optimizer import mesh_relpath, optimize_all
from crungus_amongus.registry import Registry, RegistryModel
from crungus_amongus.site_export import build_site_data

STEM = "owner--model/crungus/3"
GLB_URL = "https://assets.meshy.example/task-1/model.glb?Expires=1"


def make_settings(tmp_path: Path) -> Settings:
    return Settings(
        replicate_api_token="test-token",
        data_dir=tmp_path / "data",
        state_dir=tmp_path / "state",
    )


def queue(settings: Settings, *keys: str) -> None:
    for key in keys:
        path = settings.originals_dir / f"{key.removesuffix('.avif')}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (8, 8)).save(path)
    settings.mesh_queue_path.write_text(f"images = {json.dumps(list(keys))}\n")


class FakeMeshy:
    """Meshy's three endpoints, with a task that finishes after `polls` polls."""

    def __init__(self, polls: int = 1, status: str = "SUCCEEDED") -> None:
        self.polls = polls
        self.status = status
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.method == "POST":
            return httpx.Response(202, json={"result": "task-1"})
        if request.url.host == "assets.meshy.example":
            return httpx.Response(200, content=b"glTF-bytes")
        self.polls -= 1
        if self.polls > 0:
            return httpx.Response(200, json={"status": "IN_PROGRESS", "progress": 50})
        return httpx.Response(
            200,
            json={
                "status": self.status,
                "progress": 100,
                "model_urls": {"glb": GLB_URL},
                "consumed_credits": 30 if self.status == "SUCCEEDED" else 0,
                "task_error": {"message": "could not reconstruct"},
            },
        )

    def created(self) -> int:
        return sum(1 for r in self.requests if r.method == "POST")


def run(
    settings: Settings,
    fake: Callable[[httpx.Request], httpx.Response],
    timeout_s: float = 5.0,
) -> dict:
    async def go() -> dict:
        async with httpx.AsyncClient(transport=httpx.MockTransport(fake)) as http:
            client = MeshyClient(http, "meshy-key", poll_interval_s=0.01)
            jobs = plan_meshes(settings)
            return await run_meshes(
                jobs, settings, client, concurrency=2, timeout_s=timeout_s
            )

    return asyncio.run(go())


def test_queue_takes_site_keys_and_rejects_unknown_images(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    queue(settings, f"{STEM}.avif")
    assert load_queue(settings) == [STEM]

    settings.mesh_queue_path.write_text('images = ["nobody/crungus/0.avif"]\n')
    with pytest.raises(ValueError, match="nobody/crungus/0"):
        load_queue(settings)

    # an SVG model's original: a .png suffix over SVG text
    svg = settings.originals_dir / "owner--model-svg/crungus/0.png"
    svg.parent.mkdir(parents=True)
    svg.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    settings.mesh_queue_path.write_text('images = ["owner--model-svg/crungus/0"]\n')
    with pytest.raises(ValueError, match="no PNG, JPEG or WebP"):
        load_queue(settings)


def test_a_mesh_is_submitted_collected_and_recorded(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    queue(settings, f"{STEM}.avif")
    fake = FakeMeshy(polls=2)

    assert run(settings, fake) == {"succeeded": 1}

    create = next(r for r in fake.requests if r.method == "POST")
    assert json.loads(create.content)["image_url"].startswith("data:image/png;base64,")
    assert create.headers["authorization"] == "Bearer meshy-key"
    # the presigned asset URL never sees the API key
    download = next(r for r in fake.requests if r.url.host == "assets.meshy.example")
    assert "authorization" not in download.headers
    assert mesh_original(settings, STEM, "task-1").read_bytes() == b"glTF-bytes"

    rows = settings.mesh_manifest_path.read_text().splitlines()
    assert [json.loads(r)["status"] for r in rows] == ["submitted", "succeeded"]
    assert json.loads(rows[0])["params"]["ai_model"] == "meshy-7.1"
    assert plan_meshes(settings) == []


def test_a_timed_out_task_is_resumed_rather_than_paid_for_again(
    tmp_path: Path,
) -> None:
    settings = make_settings(tmp_path)
    queue(settings, STEM)
    stalled = FakeMeshy(polls=10_000)

    assert run(settings, stalled, timeout_s=0.05) == {"pending": 1}
    assert load_mesh_manifest(settings.mesh_manifest_path)[STEM].status == ("submitted")

    resumed = FakeMeshy(polls=1)
    assert run(settings, resumed) == {"succeeded": 1}
    assert resumed.created() == 0


def test_a_failed_task_stays_failed_until_asked(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    queue(settings, STEM)

    assert run(settings, FakeMeshy(status="FAILED")) == {"failed": 1}
    entry = load_mesh_manifest(settings.mesh_manifest_path)[STEM]
    assert entry.error == "could not reconstruct"
    assert plan_meshes(settings) == []
    assert [j.stem for j in plan_meshes(settings, retry_failed=True)] == [STEM]


def test_a_rejected_request_records_nothing(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    queue(settings, STEM)

    def broke(request: httpx.Request) -> httpx.Response:
        return httpx.Response(402, json={"message": "insufficient credits"})

    with pytest.raises(ExceptionGroup):
        run(settings, broke)
    assert not settings.mesh_manifest_path.exists()


def minimal_glb() -> bytes:
    """One triangle: the smallest GLB gltf-transform will optimise."""
    positions = struct.pack("<9f", 0, 0, 0, 1, 0, 0, 0, 1, 0)
    gltf = {
        "asset": {"version": "2.0"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}],
        "accessors": [
            {
                "bufferView": 0,
                "componentType": 5126,
                "count": 3,
                "type": "VEC3",
                "min": [0, 0, 0],
                "max": [1, 1, 0],
            }
        ],
        "bufferViews": [{"buffer": 0, "byteLength": len(positions)}],
        "buffers": [{"byteLength": len(positions)}],
    }
    text = json.dumps(gltf).encode()
    text += b" " * (-len(text) % 4)
    body = (
        struct.pack("<I4s", len(text), b"JSON")
        + text
        + struct.pack("<I4s", len(positions), b"BIN\0")
        + positions
    )
    return struct.pack("<4sII", b"glTF", 2, 12 + len(body)) + body


def test_an_encoded_mesh_is_published_and_synced_immutable(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    queue(settings, STEM)
    optimized = settings.optimized_dir / f"{STEM}.avif"
    optimized.parent.mkdir(parents=True)
    optimized.write_bytes(b"avif")
    raw = mesh_original(settings, STEM, "task-1")
    raw.parent.mkdir(parents=True)
    raw.write_bytes(minimal_glb())
    now = datetime.now(tz=UTC)
    append_mesh_entry(
        settings.mesh_manifest_path,
        MeshEntry(image=STEM, task_id="task-1", status="succeeded", created_at=now),
    )
    registry = Registry(
        fetched_at=now,
        models=[
            RegistryModel(
                owner="owner",
                name="model",
                slug="owner--model",
                source="collection",
                version_id="v1",
            )
        ],
    )

    # recorded but not yet encoded: nothing to link
    assert (
        build_site_data(registry, settings).models[0].prompts[0].images[0].mesh is None
    )

    optimize_all(settings)
    key = f"meshes/{mesh_relpath(STEM, 'task-1')}"
    image = build_site_data(registry, settings).models[0].prompts[0].images[0]
    assert image.mesh == key
    plan = {item.key: item for item in upload_plan(settings)}
    assert plan[key].cache == CACHE_CONTROL
    # images without a mesh don't carry the field at all
    assert '"mesh"' not in image.model_copy(update={"mesh": None}).model_dump_json()
