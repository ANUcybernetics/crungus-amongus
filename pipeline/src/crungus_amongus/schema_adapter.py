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

import os
import random
import re
from typing import Any

from .config import AUDIO_DURATION_S
from .exceptions import SchemaIncompatibleError
from .registry import RegistryModel

COUNT_FIELDS = ("num_outputs", "num_images", "number_of_images", "variations")
SEED_MAX = 2**31 - 1
SAFETY_FIELD = re.compile(
    r"safety|nsfw|moderation|content_filter|censor", re.IGNORECASE
)
# the most permissive option where a provider offers a named choice rather than
# a boolean or a range; a field not listed here is left alone rather than guessed
PERMISSIVE_CHOICE = {
    "moderation": "low",
    "safety_filter_level": "block_only_high",
}
# a curated extra input of the form ${VAR} is filled from the environment
ENV_REFERENCE = re.compile(r"\$\{([A-Z][A-Z0-9_]*)\}")


def resolve_env(value: Any, ref: str) -> Any:
    """Fill a ${VAR} extra input from the environment.

    A few models are passthroughs that want the caller's own provider key.
    That key never goes in the tracked curated file: the file names the
    variable, the value comes from the untracked mise [env] block. An unset
    variable is a schema incompatibility rather than a prediction sent with a
    literal "${VAR}" in it — never guess-and-spend.
    """
    if not isinstance(value, str):
        return value
    match = ENV_REFERENCE.fullmatch(value)
    if match is None:
        return value
    resolved = os.environ.get(match[1])
    if not resolved:
        raise SchemaIncompatibleError(
            f"{ref}: {match[1]} is not set in the environment"
        )
    return resolved


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


def relax_safety(props: dict[str, Any]) -> dict[str, Any]:
    """Every safety control the model exposes, set as permissive as it goes.

    The archive is a record of what a model draws, not of what its host will
    show. Leaving these at their defaults corrupts the corpus in two ways: a
    loud refusal costs a sample, and a silent one is worse — Replicate's
    latent-consistency-model returned sixteen pure-black frames that the
    manifest recorded as successes. Applied wherever a control exists; the
    59 models without one are simply asked as they are.
    """
    payload: dict[str, Any] = {}
    for field, spec in props.items():
        if not SAFETY_FIELD.search(field):
            continue
        if spec.get("type") == "boolean" or isinstance(spec.get("default"), bool):
            # disable_safety_checker → on, enable_safety_checker → off
            payload[field] = field.startswith("disable")
        elif spec.get("maximum") is not None:
            payload[field] = spec["maximum"]
        elif field in PERMISSIVE_CHOICE:
            payload[field] = PERMISSIVE_CHOICE[field]
    return payload


def build_input(model: RegistryModel, prompt: str) -> dict[str, Any]:
    payload: dict[str, Any] = {find_prompt_field(model): prompt}
    props: dict[str, Any] = (model.input_schema or {}).get("properties", {})
    for field in COUNT_FIELDS:
        if field in props:
            payload[field] = 1
    if "seed" in props:
        payload["seed"] = random.randint(0, SEED_MAX)
    payload.update(relax_safety(props))
    if model.modality == "audio" and "duration" in props:
        payload["duration"] = _clamp(AUDIO_DURATION_S, props["duration"])
    payload.update(
        {k: resolve_env(v, model.ref) for k, v in model.extra_inputs.items()}
    )
    return payload


def _clamp(value: int, field: dict[str, Any]) -> int:
    low = field.get("minimum")
    high = field.get("maximum")
    if low is not None:
        value = max(value, int(low))
    if high is not None:
        value = min(value, int(high))
    return value
