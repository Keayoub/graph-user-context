"""FastAPI dependencies for configuration and bearer assertions."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from graph_context.auth.token_validation import TokenValidator
from graph_context.config import Settings

bearer = HTTPBearer(auto_error=False)


def require_assertion(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),  # noqa: B008
) -> str:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer access token required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


def validator(settings: Settings) -> TokenValidator:
    return TokenValidator(settings)
