"""Thin async Replicate predictions client over httpx.

Deliberately not the official `replicate` package: we need explicit
per-prediction timeout, cancellation, retry classification, and raw output
payloads for normalisation — a direct API wrapper is simpler than working
around the client's blocking/FileOutput conveniences.
"""

import asyncio
from typing import Any

import httpx
from loguru import logger

from .config import REPLICATE_API_BASE
from .exceptions import (
    NsfwBlockedError,
    PermanentPredictionError,
    RetryablePredictionError,
)

TERMINAL_STATUSES = {"succeeded", "failed", "canceled"}
POLL_INTERVAL_S = 3.0

NSFW_MARKERS = ("nsfw", "sensitive", "safety", "flagged")
# model ran but the failure is upstream-transient, not a property of the input
TRANSIENT_MARKERS = ("temporarily unavailable", "try again", "director:")


class ReplicateClient:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def run_prediction(
        self,
        *,
        owner: str,
        name: str,
        version_id: str,
        is_official: bool,
        payload: dict[str, Any],
        timeout_s: float,
    ) -> dict[str, Any]:
        """Create a prediction, wait for a terminal state, and classify failures.

        Returns the terminal prediction object on success. Raises
        Retryable/Permanent/NsfwBlocked errors for the caller's retry policy.
        """
        prediction_id: str | None = None
        try:
            async with asyncio.timeout(timeout_s):
                prediction = await self._create(
                    owner, name, version_id, is_official, payload
                )
                prediction_id = prediction.get("id")
                prediction = await self._wait(prediction)
        except TimeoutError:
            if prediction_id:
                await self._cancel(prediction_id)
            raise RetryablePredictionError(
                f"timed out after {timeout_s:.0f}s"
            ) from None

        if prediction["status"] == "succeeded":
            return prediction
        error = str(prediction.get("error") or f"status {prediction['status']}")
        lowered = error.lower()
        if any(marker in lowered for marker in NSFW_MARKERS):
            raise NsfwBlockedError(error)
        if any(marker in lowered for marker in TRANSIENT_MARKERS):
            raise RetryablePredictionError(error)
        raise PermanentPredictionError(error)

    async def _create(
        self,
        owner: str,
        name: str,
        version_id: str,
        is_official: bool,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        body = {"input": payload}
        headers = {"Prefer": "wait=60"}
        # official models are routed by Replicate and must use the
        # model-scoped endpoint (versioned predictions die with Director
        # errors); community models honour the pinned version id.
        if is_official:
            response = await self._client.post(
                f"{REPLICATE_API_BASE}/models/{owner}/{name}/predictions",
                json=body,
                headers=headers,
            )
            return self._checked(response)
        response = await self._client.post(
            f"{REPLICATE_API_BASE}/predictions",
            json=body | {"version": version_id},
            headers=headers,
        )
        if response.status_code in (404, 422):
            logger.debug(
                "{}/{}: version endpoint rejected ({}), using model endpoint",
                owner,
                name,
                response.status_code,
            )
            response = await self._client.post(
                f"{REPLICATE_API_BASE}/models/{owner}/{name}/predictions",
                json=body,
                headers=headers,
            )
        return self._checked(response)

    async def _wait(self, prediction: dict[str, Any]) -> dict[str, Any]:
        while prediction["status"] not in TERMINAL_STATUSES:
            await asyncio.sleep(POLL_INTERVAL_S)
            response = await self._client.get(
                f"{REPLICATE_API_BASE}/predictions/{prediction['id']}"
            )
            prediction = self._checked(response)
        return prediction

    async def _cancel(self, prediction_id: str) -> None:
        try:
            await self._client.post(
                f"{REPLICATE_API_BASE}/predictions/{prediction_id}/cancel"
            )
        except httpx.HTTPError:
            logger.warning("failed to cancel prediction {}", prediction_id)

    def _checked(self, response: httpx.Response) -> dict[str, Any]:
        if response.status_code == 429 or response.status_code >= 500:
            raise RetryablePredictionError(
                f"HTTP {response.status_code}: {response.text[:200]}"
            )
        if response.status_code == 402:
            # out of credit: no point continuing the batch — let it bubble
            response.raise_for_status()
        if response.status_code >= 400:
            raise PermanentPredictionError(
                f"HTTP {response.status_code}: {response.text[:200]}"
            )
        return response.json()


async def download(client: httpx.AsyncClient, url: str) -> bytes:
    try:
        response = await client.get(url, timeout=120.0)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise RetryablePredictionError(f"download failed: {exc}") from exc
    return response.content
