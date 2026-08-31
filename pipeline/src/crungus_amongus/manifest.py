"""Append-only prediction manifest (state/manifest.jsonl).

One JSON line per terminal state transition; the effective state is the last
line per idempotency key. A crash mid-prediction leaves no line, so the item
is simply retried on the next run.
"""

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

type Status = Literal[
    "succeeded",
    "failed_retryable",
    "failed_permanent",
    "nsfw_blocked",
    "timeout",
    "schema_incompatible",
]

# statuses never retried automatically (without --retry-failed)
PERMANENT_STATUSES: frozenset[str] = frozenset(
    {"succeeded", "nsfw_blocked", "schema_incompatible", "failed_permanent"}
)


class ManifestEntry(BaseModel):
    owner: str
    name: str
    version_id: str
    prompt_slug: str
    image_index: int
    status: Status
    prediction_id: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
    predict_time_s: float | None = None
    wall_time_s: float | None = None
    error: str | None = None
    output_path: str | None = None

    @property
    def key(self) -> tuple[str, str, str, str, int]:
        return (
            self.owner,
            self.name,
            self.version_id,
            self.prompt_slug,
            self.image_index,
        )


def append_entry(path: Path, entry: ManifestEntry) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(entry.model_dump_json() + "\n")


def load_manifest(path: Path) -> dict[tuple[str, str, str, str, int], ManifestEntry]:
    """Reduce the append-only log to the latest entry per key."""
    entries: dict[tuple[str, str, str, str, int], ManifestEntry] = {}
    if not path.exists():
        return entries
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                entry = ManifestEntry.model_validate_json(line)
                entries[entry.key] = entry
    return entries
