"""Coerce heterogeneous prediction outputs into image URLs."""

from typing import Any
from urllib.parse import urlparse

from .exceptions import PermanentPredictionError
from .registry import RegistryModel

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif"}
DEFAULT_EXTENSION = ".png"


def output_urls(model: RegistryModel, output: Any) -> list[str]:
    """Normalise prediction.output to a non-empty list of URL strings."""
    if model.output_field and isinstance(output, dict):
        output = output.get(model.output_field)
    match output:
        case str() as url if url.startswith("http"):
            return [url]
        case list() as items if items and all(
            isinstance(u, str) and u.startswith("http") for u in items
        ):
            return items
        case _:
            raise PermanentPredictionError(
                f"{model.ref}: unrecognised output shape: {type(output).__name__}"
            )


def url_extension(url: str) -> str:
    path = urlparse(url).path
    for ext in IMAGE_EXTENSIONS:
        if path.lower().endswith(ext):
            return ".jpg" if ext == ".jpeg" else ext
    return DEFAULT_EXTENSION
