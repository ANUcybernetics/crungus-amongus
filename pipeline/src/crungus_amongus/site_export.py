"""Assemble the site data contract (site/src/data/models.json).

Built from registry + manifest + analysis + what actually exists under
data/optimized/, so the site never links an image that didn't survive the
whole pipeline.
"""

import re
from collections import Counter, defaultdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

from loguru import logger
from pydantic import BaseModel

from .analyzer import Analysis, load_analysis
from .config import (
    OUTPUTS_PER_PROMPT,
    PROMPTS,
    REPO_ROOT,
    SAFETY_DEFAULTS_UNTIL,
    Modality,
    Settings,
)
from .manifest import ManifestEntry, load_manifest, read_manifest
from .registry import Registry, RegistryModel

SITE_DATA_PATH = REPO_ROOT / "site" / "src" / "data" / "models.json"


class ImageRef(BaseModel):
    key: str  # "<slug>/<prompt_slug>/<index>.avif", relative to image_base_url
    atlas: tuple[float, float] | None = None
    typicality: float | None = None  # mean cos sim to the release year's images


class ClipRef(BaseModel):
    # both keys relative to image_base_url; the site plays opus where the
    # browser can and falls back to m4a (Safari on macOS)
    opus: str  # "<slug>/<prompt_slug>/<index>.opus"
    m4a: str  # "<slug>/<prompt_slug>/<index>.m4a"


class Attempts(BaseModel):
    """How the asking went for the images the corpus actually holds.

    The latest attempt per slot, so it describes the corpus as it stands, and
    for the model's currently pinned version only — a version change
    invalidates earlier work.
    """

    total: int
    succeeded: int
    refused: int  # the provider's own classifier rejected the output
    failed: int  # everything else terminal: errors, timeouts, bad schemas


class Refusals(BaseModel):
    """What the provider's default safety filter did, before it was turned off.

    A dated historical measurement rather than a live statistic. Every model
    exposing a safety control is now asked with it as permissive as it goes
    (see schema_adapter.relax_safety), so a refusal rate computed today would
    describe our configuration and not theirs. This counts only predictions
    made before config.SAFETY_DEFAULTS_UNTIL, and stops moving thereafter.
    """

    measured_until: datetime
    asked: int
    refused: int


class PromptOutputs(BaseModel):
    prompt: str
    prompt_slug: str
    consistency: float | None = None
    attempts: Attempts
    refusals: Refusals
    images: list[ImageRef]  # image models
    clips: list[ClipRef]  # audio models


class ModelEntry(BaseModel):
    slug: str
    owner: str
    name: str
    modality: Modality
    version_id: str | None
    description: str | None
    source: Literal["collection", "legacy"]
    is_official: bool
    release_date: date | None
    replicate_url: str
    status: Literal["ok", "partial", "failed", "incompatible", "unavailable", "pending"]
    prompts: list[PromptOutputs]
    notes: str | None


class SiteData(BaseModel):
    generated_at: datetime
    image_base_url: str
    models: list[ModelEntry]


def attempt_counts(
    manifest: dict[tuple[str, str, str, str, int], ManifestEntry],
) -> dict[tuple[str, str, str, str], Counter[str]]:
    """Terminal statuses grouped by (owner, name, version, prompt slug)."""
    counts: dict[tuple[str, str, str, str], Counter[str]] = defaultdict(Counter)
    for (owner, name, version, prompt_slug, _), entry in manifest.items():
        counts[(owner, name, version, prompt_slug)][entry.status] += 1
    return counts


def refusal_counts(settings: Settings) -> dict[tuple[str, str, str], Counter[str]]:
    """Default-filter-era asks and refusals per (owner, name, prompt slug).

    Read from the whole append-only log rather than its latest state, because a
    refusal that was later re-rolled into a success still happened — and this
    is a record of what the filters did, not of what the corpus holds. Version
    is deliberately not part of the key: the measurement is about the provider's
    filter, which outlives any one pin.
    """
    counts: dict[tuple[str, str, str], Counter[str]] = defaultdict(Counter)
    for entry in read_manifest(settings.manifest_path):
        if entry.created_at < SAFETY_DEFAULTS_UNTIL:
            counts[(entry.owner, entry.name, entry.prompt_slug)][entry.status] += 1
    return counts


def build_site_data(registry: Registry, settings: Settings) -> SiteData:
    manifest = load_manifest(settings.manifest_path)
    counts = attempt_counts(manifest)
    refusals = refusal_counts(settings)
    analysis = load_analysis(settings)
    models = [
        _model_entry(model, counts, refusals, analysis, settings)
        for model in registry.models
    ]
    models.sort(key=lambda m: (m.release_date or date.max, m.slug))
    return SiteData(
        generated_at=datetime.now(tz=UTC),
        image_base_url=settings.image_base_url,
        models=models,
    )


_NUMBER = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?")


def inline_short_arrays(text: str, width: int = 80) -> str:
    """Collapse all-numeric arrays onto one line when they fit, as oxfmt does.

    The site treats models.json as a formatted source file, so what `publish`
    writes has to already be a fixed point of `pnpm run format` — otherwise
    every regeneration reflows the file and CI's format check fails.
    """
    lines = text.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.rstrip().endswith("["):
            close = next(
                (
                    j
                    for j in range(i + 1, len(lines))
                    if lines[j].lstrip().startswith("]")
                ),
                None,
            )
            if close is not None:
                items = [lines[j].strip() for j in range(i + 1, close)]
                if items and all(_NUMBER.fullmatch(it.rstrip(",")) for it in items):
                    joined = line.rstrip() + " ".join(items) + lines[close].lstrip()
                    if len(joined) <= width:
                        out.append(joined)
                        i = close + 1
                        continue
        out.append(line)
        i += 1
    return "\n".join(out)


def export_site_data(registry: Registry, settings: Settings, out: Path) -> SiteData:
    data = build_site_data(registry, settings)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(inline_short_arrays(data.model_dump_json(indent=2)) + "\n")
    ok = sum(1 for m in data.models if m.status == "ok")
    total_images = sum(len(p.images) for m in data.models for p in m.prompts)
    total_clips = sum(len(p.clips) for m in data.models for p in m.prompts)
    logger.info(
        "site data: {} models ({} complete), {} images, {} clips → {}",
        len(data.models),
        ok,
        total_images,
        total_clips,
        out,
    )
    return data


def _model_entry(
    model: RegistryModel,
    counts: dict[tuple[str, str, str, str], Counter[str]],
    refusals: dict[tuple[str, str, str], Counter[str]],
    analysis: Analysis | None,
    settings: Settings,
) -> ModelEntry:
    prompts: list[PromptOutputs] = []
    for prompt_slug, prompt in PROMPTS[model.modality].items():
        images: list[ImageRef] = []
        clips: list[ClipRef] = []
        for index in range(OUTPUTS_PER_PROMPT[model.modality]):
            stem = f"{model.slug}/{prompt_slug}/{index}"
            optimized = settings.optimized_dir / stem
            if model.modality == "audio":
                if all(optimized.with_suffix(s).exists() for s in (".opus", ".m4a")):
                    clips.append(ClipRef(opus=f"{stem}.opus", m4a=f"{stem}.m4a"))
                continue
            if not optimized.with_suffix(".avif").exists():
                continue
            atlas = analysis.atlas.get(stem) if analysis else None
            typicality = analysis.year_typicality.get(stem) if analysis else None
            images.append(
                ImageRef(key=f"{stem}.avif", atlas=atlas, typicality=typicality)
            )
        consistency = (
            analysis.consistency.get(f"{model.slug}/{prompt_slug}")
            if analysis
            else None
        )
        tally = counts.get(
            (model.owner, model.name, model.version_id or "", prompt_slug), Counter()
        )
        refused = tally["nsfw_blocked"]
        succeeded = tally["succeeded"]
        total = sum(tally.values())
        historic = refusals.get((model.owner, model.name, prompt_slug), Counter())
        prompts.append(
            PromptOutputs(
                prompt=prompt,
                prompt_slug=prompt_slug,
                consistency=consistency,
                refusals=Refusals(
                    measured_until=SAFETY_DEFAULTS_UNTIL,
                    asked=sum(historic.values()),
                    refused=historic["nsfw_blocked"],
                ),
                attempts=Attempts(
                    total=total,
                    succeeded=succeeded,
                    refused=refused,
                    failed=total - succeeded - refused,
                ),
                images=images,
                clips=clips,
            )
        )

    total = sum(len(p.images) + len(p.clips) for p in prompts)
    expected = len(PROMPTS[model.modality]) * OUTPUTS_PER_PROMPT[model.modality]
    if model.availability != "ok":
        status: Literal[
            "ok", "partial", "failed", "incompatible", "unavailable", "pending"
        ] = "unavailable"
    elif total == expected:
        status = "ok"
    elif total > 0:
        status = "partial"
    else:
        # every version's rows, not just the pinned one: a model that only ever
        # failed under an older pin has still been asked
        manifest_statuses = {
            status
            for (owner, name, _, _), tally in counts.items()
            if owner == model.owner and name == model.name
            for status in tally
        }
        if not manifest_statuses:
            status = "pending"  # batch has not reached this model yet
        elif "schema_incompatible" in manifest_statuses:
            status = "incompatible"
        else:
            status = "failed"

    return ModelEntry(
        slug=model.slug,
        owner=model.owner,
        name=model.name,
        modality=model.modality,
        version_id=model.version_id,
        description=model.description,
        source=model.source,
        is_official=model.is_official,
        release_date=model.release_date
        or (model.version_created_at.date() if model.version_created_at else None),
        replicate_url=f"https://replicate.com/{model.owner}/{model.name}",
        status=status,
        prompts=prompts,
        notes=model.notes,
    )
