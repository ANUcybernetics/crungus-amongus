import json

from crungus_amongus.site_export import inline_short_arrays


def test_inlines_a_numeric_array_that_fits() -> None:
    text = json.dumps({"atlas": [0.1691, 0.4071]}, indent=2)
    assert inline_short_arrays(text) == '{\n  "atlas": [0.1691, 0.4071]\n}'


def test_keeps_the_trailing_comma_on_a_collapsed_array() -> None:
    text = json.dumps({"atlas": [0.1, 0.2], "typicality": 0.98}, indent=2)
    assert '"atlas": [0.1, 0.2],' in inline_short_arrays(text)


def test_leaves_arrays_of_objects_expanded() -> None:
    text = json.dumps({"images": [{"key": "a"}]}, indent=2)
    assert inline_short_arrays(text) == text


def test_leaves_a_numeric_array_too_wide_to_fit_expanded() -> None:
    text = json.dumps({"xs": [1.123456789] * 12}, indent=2)
    assert inline_short_arrays(text) == text


def test_round_trips_to_equivalent_json() -> None:
    payload = {"models": [{"atlas": [0.1691, 0.4071], "images": []}]}
    text = json.dumps(payload, indent=2)
    assert json.loads(inline_short_arrays(text)) == payload
