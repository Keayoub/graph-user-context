"""Minimal async Graph transport with safe retries and pagination."""

from __future__ import annotations

import asyncio
import logging
import random
import uuid
from collections.abc import AsyncIterator
from typing import Any, Protocol, cast

import httpx

logger = logging.getLogger(__name__)


class AsyncTokenCredential(Protocol):
    async def get_token(self, *scopes: str, **kwargs: Any) -> Any: ...

    async def close(self) -> None: ...


class GraphRequestError(RuntimeError):
    """A non-retryable or exhausted Graph request failure."""

    def __init__(self, status_code: int, message: str, request_id: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.request_id = request_id


class GraphClient:
    def __init__(
        self,
        credential: AsyncTokenCredential,
        *,
        base_url: str = "https://graph.microsoft.com/v1.0",
        concurrency: int = 8,
        max_retries: int = 6,
        timeout: float = 45.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.credential = credential
        self.base_url = base_url.rstrip("/")
        self.semaphore = asyncio.Semaphore(concurrency)
        self.max_retries = max_retries
        self.client = http_client or httpx.AsyncClient(timeout=httpx.Timeout(timeout))
        self._owns_client = http_client is None

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    async def get(self, path_or_url: str) -> dict[str, Any]:
        url = path_or_url if path_or_url.startswith("https://") else f"{self.base_url}{path_or_url}"
        for attempt in range(self.max_retries + 1):
            token = await self.credential.get_token("https://graph.microsoft.com/.default")
            request_id = str(uuid.uuid4())
            async with self.semaphore:
                response = await self.client.get(
                    url,
                    headers={
                        "Authorization": f"Bearer {token.token}",
                        "Accept": "application/json",
                        "client-request-id": request_id,
                        "return-client-request-id": "true",
                    },
                )
            if response.is_success:
                return cast(dict[str, Any], response.json())

            retryable = response.status_code == 429 or 500 <= response.status_code <= 599
            if not retryable or attempt >= self.max_retries:
                graph_request_id = response.headers.get("request-id")
                raise GraphRequestError(
                    response.status_code,
                    f"Graph request failed with HTTP {response.status_code}",
                    graph_request_id,
                )
            delay = self._retry_delay(response, attempt)
            logger.warning(
                "Graph retry status=%s attempt=%s delay=%.2f request_id=%s",
                response.status_code,
                attempt + 1,
                delay,
                response.headers.get("request-id", request_id),
            )
            await asyncio.sleep(delay)
        raise AssertionError("retry loop exited unexpectedly")

    @staticmethod
    def _retry_delay(response: httpx.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return float(min(120.0, max(0.0, float(retry_after))))
            except ValueError:
                pass
        return float(min(120.0, (2**attempt) + random.uniform(0.0, 1.0)))

    async def pages(self, path_or_url: str) -> AsyncIterator[list[dict[str, Any]]]:
        next_url: str | None = path_or_url
        while next_url:
            payload = await self.get(next_url)
            yield payload.get("value", [])
            next_url = payload.get("@odata.nextLink")

    async def all_items(self, path_or_url: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        async for page in self.pages(path_or_url):
            items.extend(page)
        return items

    async def delta(
        self, delta_url: str | None, select: list[str]
    ) -> tuple[list[dict[str, Any]], str | None]:
        path = delta_url or f"/users/delta?$select={','.join(select)}"
        changes: list[dict[str, Any]] = []
        final_link: str | None = None
        next_url: str | None = path
        while next_url:
            payload = await self.get(next_url)
            changes.extend(payload.get("value", []))
            next_url = payload.get("@odata.nextLink")
            final_link = payload.get("@odata.deltaLink", final_link)
        return changes, final_link
