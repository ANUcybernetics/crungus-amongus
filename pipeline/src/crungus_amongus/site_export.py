"""Assemble the site data contract (site/src/data/models.json).

Built from registry + manifest + analysis + what actually exists under
data/optimized/, so the site never links an image that didn't survive the
whole pipeline.
"""

import re
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

from loguru import logger
from pydantic import BaseModel

from .analyzer import Analysis, load_analysis
from .config import IMAGES_PER_PROMPT, PROMPTS, REPO_ROOT, Settings
from .manifest import ManifestEntry, load_manifest
from .registry import Registry, RegistryModel

SITE_DATA_PATH = REPO_ROOT / "site" / "src" / "data" / "models.json"


class ImageRef(BaseModel):
    key: str  # "<slug>/<prompt_slug>/<index>.avif", relative to image_base_url
    atlas: tuple[float, float] | None = None
    typicality: float | None = None  # mean cos sim to the release year's images


class PromptImages(BaseModel):
    prompt: str
    prompt_slug: str
    consistency: float | None = None
    images: list[ImageRef]


class ModelEntry(BaseModel):
    slug: str
    owner: str
    name: str
    version_id: str | None
    description: str | None
    source: Literal["collection", "legacy"]
    is_official: bool
    release_date: date | None
    replicate_url: str
    status: Literal["ok", "partial", "failed", "incompatible", "unavailable", "pending"]
    prompts: list[PromptImages]
    notes: str | None


class SiteData(BaseModel):
    generated_at: datetime
    image_base_url: str
    models: list[ModelEntry]


def build_site_data(registry: Registry, settings: Settings) -> SiteData:
    manifest = load_manifest(settings.manifest_path)
    analysis = load_analysis(settings)
    models = [
        _model_entry(model, manifest, analysis, settings) for model in registry.models
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
    logger.info(
        "site data: {} models ({} complete), {} images → {}",
        len(data.models),
        ok,
        total_images,
        out,
    )
    return data


def _model_entry(
    model: RegistryModel,
    manifest: dict[tuple[str, str, str, str, int], ManifestEntry],
    analysis: Analysis | None,
    settings: Settings,
) -> ModelEntry:
    prompts: list[PromptImages] = []
    for prompt_slug, prompt in PROMPTS.items():
        images: list[ImageRef] = []
        for index in range(IMAGES_PER_PROMPT):
            avif = settings.optimized_dir / model.slug / prompt_slug / f"{index}.avif"
            if not avif.exists():
                continue
            atlas_key = f"{model.slug}/{prompt_slug}/{index}"
            atlas = analysis.atlas.get(atlas_key) if analysis else None
            typicality = analysis.year_typicality.get(atlas_key) if analysis else None
            images.append(
                ImageRef(
                    key=f"{model.slug}/{prompt_slug}/{index}.avif",
                    atlas=atlas,
                    typicality=typicality,
                )
            )
        consistency = (
            analysis.consistency.get(f"{model.slug}/{prompt_slug}")
            if analysis
            else None
        )
        prompts.append(
            PromptImages(
                prompt=prompt,
                prompt_slug=prompt_slug,
                consistency=consistency,
                images=images,
            )
        )

    total = sum(len(p.images) for p in prompts)
    expected = len(PROMPTS) * IMAGES_PER_PROMPT
    if model.availability != "ok":
        status: Literal[
            "ok", "partial", "failed", "incompatible", "unavailable", "pending"
        ] = "unavailable"
    elif total == expected:
        status = "ok"
    elif total > 0:
        status = "partial"
    else:
        manifest_statuses = {
            e.status
            for e in manifest.values()
            if e.owner == model.owner and e.name == model.name
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
