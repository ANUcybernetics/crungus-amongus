"""Build a minimal prediction input for a model from its OpenAPI Input schema.

Policy: prompt field + curated extra_inputs + schema defaults only. Never set
width/height/guidance. Set an explicit random seed where the schema has one:
the cog convention says an omitted seed randomises, but some models ship a
fixed default and returned ten identical images. Force any output-count field
to 1 so one prediction = one image. No confident prompt field →
SchemaIncompatibleError; never guess-and-spend.
"""

import random
from typing import Any

from .exceptions import SchemaIncompatibleError
from .registry import RegistryModel

COUNT_FIELDS = ("num_outputs", "num_images", "number_of_images")
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
    payload.update(model.extra_inputs)
    return payload
