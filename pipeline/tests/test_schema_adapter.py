from typing import Any

import pytest

from crungus_amongus.config import AUDIO_DURATION_S, Modality
from crungus_amongus.exceptions import SchemaIncompatibleError
from crungus_amongus.registry import RegistryModel
from crungus_amongus.schema_adapter import build_input, find_prompt_field


def make_model(
    properties: dict[str, Any],
    prompt_field: str | None = None,
    extra_inputs: dict[str, Any] | None = None,
    modality: Modality = "image",
) -> RegistryModel:
    return RegistryModel(
        owner="test",
        name="model",
        slug="test--model",
        source="collection",
        modality=modality,
        version_id="v1",
        input_schema={"properties": properties},
        prompt_field=prompt_field,
        extra_inputs=extra_inputs or {},
    )


def test_standard_sd_style_schema() -> None:
    model = make_model(
        {
            "prompt": {"type": "string"},
            "width": {"type": "integer", "default": 768},
            "num_outputs": {"type": "integer", "default": 1},
            "seed": {"type": "integer"},
        }
    )
    payload = build_input(model, "crungus")
    assert payload["prompt"] == "crungus"
    assert payload["num_outputs"] == 1
    assert isinstance(payload["seed"], int)  # explicit random seed when field exists


def test_min_dalle_style_override() -> None:
    model = make_model(
        {"text": {"type": "string"}, "grid_size": {"type": "integer"}},
        prompt_field="text",
        extra_inputs={"grid_size": 1},
    )
    assert build_input(model, "crungus") == {
        "text": "crungus",
        "grid_size": 1,
    }  # no seed field


def test_text_field_fallback() -> None:
    model = make_model({"text": {"type": "string"}})
    assert find_prompt_field(model) == "text"


def test_no_prompt_field_refuses() -> None:
    model = make_model({"instruction": {"type": "string"}})
    with pytest.raises(SchemaIncompatibleError):
        build_input(model, "crungus")


def test_audio_duration_is_fixed_and_clamped() -> None:
    model = make_model(
        {"prompt": {"type": "string"}, "duration": {"type": "integer", "default": 190}},
        modality="audio",
    )
    assert build_input(model, "crungus")["duration"] == AUDIO_DURATION_S
    short = make_model(
        {"prompt": {"type": "string"}, "duration": {"maximum": 8}}, modality="audio"
    )
    assert build_input(short, "crungus")["duration"] == 8
    image = make_model({"prompt": {"type": "string"}, "duration": {"default": 8}})
    assert "duration" not in build_input(image, "crungus")


def test_variations_count_field_forced_to_one() -> None:
    model = make_model(
        {"prompt": {"type": "string"}, "variations": {"default": 3}}, modality="audio"
    )
    assert build_input(model, "crungus")["variations"] == 1
