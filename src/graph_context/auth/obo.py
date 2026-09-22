"""MSAL On-Behalf-Of token exchange."""

from __future__ import annotations

import asyncio
from typing import Any

import msal  # type: ignore[import-untyped]
from fastapi import HTTPException, status

from graph_context.config import Settings


class OboTokenService:
    def __init__(self, settings: Settings, application: Any | None = None) -> None:
        settings.validate_obo()
        assert settings.obo_tenant_id and settings.obo_client_id and settings.obo_client_secret
        self.application = application or msal.ConfidentialClientApplication(
            client_id=settings.obo_client_id,
            client_credential=settings.obo_client_secret.get_secret_value(),
            authority=f"https://login.microsoftonline.com/{settings.obo_tenant_id}",
        )

    async def exchange(self, assertion: str) -> str:
        result = await asyncio.to_thread(
            self.application.acquire_token_on_behalf_of,
            user_assertion=assertion,
            scopes=["https://graph.microsoft.com/.default"],
        )
        token = result.get("access_token")
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="On-Behalf-Of consent or token exchange failed",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return str(token)
