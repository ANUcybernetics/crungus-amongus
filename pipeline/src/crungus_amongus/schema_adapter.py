"""Build a minimal prediction input for a model from its OpenAPI Input schema.

Policy: prompt field + curated extra_inputs + schema defaults only. Never set
width/height/guidance. Set an explicit random seed where the schema has one:
the cog convention says an omitted seed randomises, but some models ship a
fixed default and returned ten identical images. Force any output-count field
to 1 so one prediction = one output. Audio models get the fixed clip length
where the schema has a `duration` (clamped to its bounds); differently-named
length fields are set per model in the curated file. No confident prompt
field → SchemaIncompatibleError; never guess-and-spend.
"""

import random
from typing import Any

from .config import AUDIO_DURATION_S
from .exceptions import SchemaIncompatibleError
from .registry import RegistryModel

COUNT_FIELDS = ("num_outputs", "num_images", "number_of_images", "variations")
SEED_MAX = 2**31 - 1


def find_prompt_field(model: RegistryModel) -> str:
    if model.prompt_field:
        return model.prompt_field
    props: dict[str, Any] = (model.input_schema or {}).get("properties", {})
    for candidate in ("prompt", "text"):
        if candidate in props:
            return candidate
    raise SchemaIncompatibleError(
        f"{model.ref}: no prompt-like input field in {sorted(props)}"
    )


def build_input(model: RegistryModel, prompt: str) -> dict[str, Any]:
    payload: dict[str, Any] = {find_prompt_field(model): prompt}
    props: dict[str, Any] = (model.input_schema or {}).get("properties", {})
    for field in COUNT_FIELDS:
        if field in props:
            payload[field] = 1
    if "seed" in props:
        payload["seed"] = random.randint(0, SEED_MAX)
    if model.modality == "audio" and "duration" in props:
        payload["duration"] = _clamp(AUDIO_DURATION_S, props["duration"])
    payload.update(model.extra_inputs)
    return payload


def _clamp(value: int, field: dict[str, Any]) -> int:
    low = field.get("minimum")
    high = field.get("maximum")
    if low is not None:
        value = max(value, int(low))
    if high is not None:
        value = min(value, int(high))
    return value
