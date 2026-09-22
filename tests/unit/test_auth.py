from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from graph_context.auth.obo import OboTokenService
from graph_context.config import Settings


@pytest.mark.asyncio
async def test_obo_exchange_returns_access_token() -> None:
    application = MagicMock()
    application.acquire_token_on_behalf_of.return_value = {"access_token": "graph-token"}
    settings = Settings(
        OBO_TENANT_ID="tenant",
        OBO_CLIENT_ID="client",
        OBO_CLIENT_SECRET="secret",
        EXPECTED_TOKEN_AUDIENCE="api://client",
    )
    service = OboTokenService(settings, application=application)
    assert await service.exchange("assertion") == "graph-token"
    application.acquire_token_on_behalf_of.assert_called_once()
