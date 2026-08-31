"""The crungus CLI: sequential, independently-runnable, idempotent stages."""

import httpx
import typer
from loguru import logger

from .config import Settings
from .logging_setup import setup_logging
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
