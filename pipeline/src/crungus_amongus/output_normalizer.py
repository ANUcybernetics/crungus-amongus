"""Coerce heterogeneous prediction outputs into output-file URLs."""

from typing import Any
from urllib.parse import urlparse

from .config import Modality
from .exceptions import PermanentPredictionError
from .registry import RegistryModel

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif"}
AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg", ".opus", ".m4a", ".aac", ".webm"}
EXTENSIONS: dict[Modality, set[str]] = {
    "image": IMAGE_EXTENSIONS,
    "audio": AUDIO_EXTENSIONS,
}
# an extensionless URL is saved with the modality's most common container;
# the optimizer sniffs the real format anyway
DEFAULT_EXTENSION: dict[Modality, str] = {"image": ".png", "audio": ".wav"}


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


def url_extension(url: str, modality: Modality = "image") -> str:
    path = urlparse(url).path
    for ext in EXTENSIONS[modality]:
        if path.lower().endswith(ext):
            return ".jpg" if ext == ".jpeg" else ext
    return DEFAULT_EXTENSION[modality]
