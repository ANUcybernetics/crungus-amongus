"""The crungus CLI: sequential, independently-runnable, idempotent stages."""

import asyncio
from collections import Counter

import httpx
import typer
from loguru import logger

from .config import Settings
from .generator import RunPolicy, plan_work, run_batch
from .logging_setup import setup_logging
from .manifest import load_manifest
from .registry import (
    build_registry,
    fetch_collection_models,
    fetch_model,
    load_curated,
    load_deny_list,
    load_registry,
    save_registry,
)

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)


@app.callback()
def main(verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:
    setup_logging(verbose)


@app.command()
def discover(
    refresh_versions: bool = typer.Option(
        False, help="Re-pin already-pinned models to their latest version"
    ),
    no_collection: bool = typer.Option(
        False, help="Skip the collection fetch; curated models only"
    ),
) -> None:
    """Fetch the text-to-image collection, merge the curated list, pin versions."""
    settings = Settings()
    curated = load_curated(settings.curated_models_path)
    deny = load_deny_list(settings.deny_list_path)
    existing = load_registry(settings.registry_path)

    headers = {"Authorization": f"Bearer {settings.replicate_api_token}"}
    with httpx.Client(headers=headers, timeout=30.0) as client:
        collection = [] if no_collection else fetch_collection_models(client)
        logger.info("collection: {} models", len(collection))

        registry = build_registry(
            collection_payloads=collection,
            curated=curated,
            deny=deny,
            existing=existing,
            fetch_legacy=lambda owner, name: fetch_model(client, owner, name),
            refresh_versions=refresh_versions,
        )

    save_registry(registry, settings.registry_path)
    ok = sum(1 for m in registry.models if m.availability == "ok")
    unavailable = [m.ref for m in registry.models if m.availability != "ok"]
    logger.info(
        "registry: {} models pinned, {} unavailable → {}",
        ok,
        len(unavailable),
        settings.registry_path,
    )
    for ref in unavailable:
        logger.warning("unavailable: {}", ref)


@app.command()
def generate(
    models: str = typer.Option(
        None, "--models", help="fnmatch pattern on owner/name or slug"
    ),
    prompt: str = typer.Option(
        None, "--prompt", help="restrict to one prompt slug (e.g. 'crungus')"
    ),
    concurrency: int = typer.Option(4, help="max in-flight predictions"),
    timeout: float = typer.Option(300.0, help="per-prediction timeout (s)"),
    retries: int = typer.Option(2, help="retries per prediction on transient failure"),
    retry_failed: bool = typer.Option(
        False, help="also retry predictions previously marked failed_permanent"
    ),
    max_predictions: int = typer.Option(
        None, "--max-predictions", help="soft cap on predictions this run"
    ),
    assumed_cost_per_image: float = typer.Option(
        0.03, help="flat per-image estimate for --dry-run (dashboard is billing truth)"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="plan and estimate only"),
) -> None:
    """Run pending predictions (resumable; skips work already done)."""
    settings = Settings()
    registry = load_registry(settings.registry_path)
    if registry is None:
        logger.error("no registry at {} — run discover first", settings.registry_path)
        raise typer.Exit(1)

    items = plan_work(
        registry,
        settings,
        model_pattern=models,
        prompt_filter=prompt,
        retry_failed=retry_failed,
    )
    capped = items[:max_predictions] if max_predictions is not None else items
    model_count = len({i.model.ref for i in capped})
    logger.info(
        "pending: {} predictions across {} models (~${:.2f} at ${}/image)",
        len(capped),
        model_count,
        len(capped) * assumed_cost_per_image,
        assumed_cost_per_image,
    )
    if dry_run or not capped:
        return

    policy = RunPolicy(
        concurrency=concurrency,
        timeout_s=timeout,
        retries=retries,
        retry_failed=retry_failed,
        max_predictions=max_predictions,
    )
    counts = asyncio.run(run_batch(items, settings, policy))
    logger.info("run complete: {}", dict(counts))


@app.command()
def optimize(
    force: bool = typer.Option(False, help="re-encode even if up to date"),
) -> None:
    """Encode originals to AVIF under data/optimized/."""
    from .optimizer import optimize_all

    optimize_all(Settings(), force=force)


@app.command()
def analyze() -> None:
    """CLIP embeddings → crungus-ness scores + UMAP atlas coords."""
    from .analyzer import run_analysis

    run_analysis(Settings())


@app.command()
def sync(
    force: bool = typer.Option(False, help="re-upload everything"),
) -> None:
    """Upload the optimized AVIF tree to the Tigris bucket."""
    from .bucket_sync import sync_optimized

    sync_optimized(Settings(), force=force)


@app.command()
def sprite() -> None:
    """Compose the atlas sprite sheet from the optimized images."""
    from .sprite import build_sprite

    build_sprite(Settings())


@app.command()
def publish(
    out: str = typer.Option(None, "--out", help="output path for models.json"),
) -> None:
    """Assemble the site data contract from registry + manifest + analysis."""
    from pathlib import Path

    from .site_export import SITE_DATA_PATH, export_site_data

    settings = Settings()
    registry = load_registry(settings.registry_path)
    if registry is None:
        logger.error("no registry — run discover first")
        raise typer.Exit(1)
    export_site_data(registry, settings, Path(out) if out else SITE_DATA_PATH)


@app.command()
def status(
    models: str = typer.Option(None, "--models", help="fnmatch pattern filter"),
) -> None:
    """Progress and spend summary from the manifest."""
    settings = Settings()
    entries = list(load_manifest(settings.manifest_path).values())
    if models:
        import fnmatch

        entries = [e for e in entries if fnmatch.fnmatch(f"{e.owner}/{e.name}", models)]
    by_status = Counter(e.status for e in entries)
    billed = sum(e.predict_time_s or 0 for e in entries if e.status == "succeeded")
    logger.info("manifest: {} entries {}", len(entries), dict(by_status))
    logger.info("billed predict time: {:.0f}s (queue time excluded)", billed)
    per_model: Counter[str] = Counter()
    for e in entries:
        if e.status != "succeeded":
            per_model[f"{e.owner}/{e.name}"] += 1
    for ref, n in per_model.most_common(15):
        logger.info("incomplete: {} ({} non-succeeded)", ref, n)
