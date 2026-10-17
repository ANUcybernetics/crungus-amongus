import asyncio
from collections.abc import Callable

import httpx
import pytest

from crungus_amongus import replicate_client
from crungus_amongus.exceptions import (
    NsfwBlockedError,
    PermanentPredictionError,
    RetryablePredictionError,
)
from crungus_amongus.replicate_client import Prediction, ReplicateClient


def run(
    handler: Callable[[httpx.Request], httpx.Response], timeout_s: float = 5.0
) -> Prediction:
    async def go() -> Prediction:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http:
            return await ReplicateClient(http).run_prediction(
                owner="owner",
                name="model",
                version_id="v1",
                is_official=False,
                payload={"prompt": "crungus"},
                timeout_s=timeout_s,
            )

    return asyncio.run(go())


def finishing(**terminal: object) -> Callable[[httpx.Request], httpx.Response]:
    """Created as `starting`, then terminal on the first poll."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(201, json={"id": "p1", "status": "starting"})
        return httpx.Response(200, json={"id": "p1", **terminal})

    return handler


@pytest.fixture(autouse=True)
def no_poll_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(replicate_client, "POLL_INTERVAL_S", 0.0)


def test_a_prediction_is_polled_to_success() -> None:
    prediction = run(
        finishing(
            status="succeeded",
            output=["https://replicate.delivery/out.png"],
            metrics={"predict_time": 2.5, "image_count": 1},
        )
    )
    assert prediction.output == ["https://replicate.delivery/out.png"]
    assert prediction.metrics is not None
    assert prediction.metrics.predict_time == 2.5


@pytest.mark.parametrize(
    ("error", "raised"),
    [
        ("NSFW content detected", NsfwBlockedError),
        ("Director: unexpected error, please try again", RetryablePredictionError),
        ("CUDA out of memory", PermanentPredictionError),
    ],
)
def test_failures_are_classified_by_message(
    error: str, raised: type[Exception]
) -> None:
    with pytest.raises(raised, match=error[:10]):
        run(finishing(status="failed", error=error))


def test_a_timed_out_prediction_is_cancelled() -> None:
    cancelled: list[str] = []

    def stuck(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/cancel"):
            cancelled.append(request.url.path)
            return httpx.Response(200, json={"id": "p1", "status": "canceled"})
        if request.method == "POST":
            return httpx.Response(201, json={"id": "p1", "status": "starting"})
        return httpx.Response(200, json={"id": "p1", "status": "processing"})

    with pytest.raises(RetryablePredictionError, match="timed out"):
        run(stuck, timeout_s=0.05)
    assert cancelled == ["/v1/predictions/p1/cancel"]
