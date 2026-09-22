from __future__ import annotations

from typing import Any

import httpx
import pytest

from graph_context.graph.client import GraphClient
from graph_context.graph.models import UserRecord
from graph_context.graph.relationships import build_manager_map
from graph_context.graph.users import normalize_user_items


class Credential:
    async def get_token(self, *_: str, **__: Any) -> Any:
        return type("Token", (), {"token": "test"})()

    async def close(self) -> None:
        return None


@pytest.mark.asyncio
async def test_pages_follow_next_link() -> None:
    requests: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        if len(requests) == 1:
            return httpx.Response(
                200, json={"value": [{"id": "1"}], "@odata.nextLink": "https://graph.test/page2"}
            )
        return httpx.Response(200, json={"value": [{"id": "2"}]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    graph = GraphClient(Credential(), base_url="https://graph.test/v1.0", http_client=client)
    try:
        assert await graph.all_items("/users") == [{"id": "1"}, {"id": "2"}]
        assert requests == ["https://graph.test/v1.0/users", "https://graph.test/page2"]
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_retry_after_429() -> None:
    attempts = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, json={"value": []})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    graph = GraphClient(Credential(), http_client=client, max_retries=1)
    try:
        assert await graph.all_items("/users") == []
        assert attempts == 2
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_reverse_manager_map_handles_missing_manager() -> None:
    class FakeGraph:
        async def all_items(self, path: str) -> list[dict[str, Any]]:
            if path.startswith("/users/manager/directReports"):
                return [{"id": "report", "displayName": "Report"}]
            return []

    users = [
        UserRecord(id="manager", displayName="Manager"),
        UserRecord(id="report", displayName="Report"),
        UserRecord(id="solo", displayName="Solo"),
    ]
    manager_map, failures = await build_manager_map(FakeGraph(), users, 2)  # type: ignore[arg-type]
    assert failures == 0
    assert manager_map["report"].id == "manager"
    assert "solo" not in manager_map


def test_limited_directory_objects_are_normalized() -> None:
    assert (
        normalize_user_items([{"id": "group", "@odata.type": "#microsoft.graph.group"}])[0]["type"]
        == "group"
    )
