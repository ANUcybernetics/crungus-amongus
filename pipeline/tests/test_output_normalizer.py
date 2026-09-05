import pytest

from crungus_amongus.exceptions import PermanentPredictionError
from crungus_amongus.output_normalizer import output_urls, url_extension
from crungus_amongus.registry import RegistryModel


def make_model(output_field: str | None = None) -> RegistryModel:
    return RegistryModel(
        owner="test",
        name="model",
        slug="test--model",
        source="collection",
        version_id="v1",
        output_field=output_field,
    )


def test_single_url() -> None:
    assert output_urls(make_model(), "https://x/y.png") == ["https://x/y.png"]


def test_url_list() -> None:
    urls = ["https://x/1.png", "https://x/2.png"]
    assert output_urls(make_model(), urls) == urls


def test_dict_with_output_field_override() -> None:
    output = {"image": "https://x/y.webp", "meta": 1}
    assert output_urls(make_model(output_field="image"), output) == ["https://x/y.webp"]


@pytest.mark.parametrize("bad", [None, [], {"weird": 1}, 42, ["https://a", 7]])
def test_unrecognised_shapes_refuse(bad: object) -> None:
    with pytest.raises(PermanentPredictionError):
        output_urls(make_model(), bad)


def test_url_extension() -> None:
    assert url_extension("https://x/y.jpeg?sig=1") == ".jpg"
    assert url_extension("https://x/y.webp") == ".webp"
    assert url_extension("https://x/y") == ".png"


def test_audio_url_extension() -> None:
    assert url_extension("https://x/y.mp3?sig=1", "audio") == ".mp3"
    assert url_extension("https://x/y.wav", "audio") == ".wav"
    assert url_extension("https://x/y", "audio") == ".wav"
    assert url_extension("https://x/y.wav") == ".png"  # image models ignore audio
