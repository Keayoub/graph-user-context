"""Local validation of access tokens issued for this API."""

from __future__ import annotations

import asyncio
from typing import Any, cast

import jwt
from fastapi import HTTPException, status

from graph_context.config import Settings


class TokenValidator:
    def __init__(self, settings: Settings) -> None:
        if not settings.obo_tenant_id or not settings.expected_audience:
            raise ValueError("OBO_TENANT_ID and EXPECTED_TOKEN_AUDIENCE are required")
        self.tenant_id = settings.allowed_tenant or settings.obo_tenant_id
        self.audience = settings.expected_audience
        authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        self.issuer = f"{authority}/v2.0"
        self.keys = jwt.PyJWKClient(f"{authority}/discovery/v2.0/keys", cache_keys=True)

    async def validate(self, token: str) -> dict[str, Any]:
        try:
            signing_key = await asyncio.to_thread(self.keys.get_signing_key_from_jwt, token)
            claims = await asyncio.to_thread(
                jwt.decode,
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self.audience,
                issuer=self.issuer,
                options={"require": ["exp", "nbf", "iat", "iss", "aud", "tid"]},
            )
            if claims.get("tid") != self.tenant_id:
                raise jwt.InvalidIssuerError("unexpected tenant")
            return cast(dict[str, Any], claims)
        except jwt.PyJWTError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid access token",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc
