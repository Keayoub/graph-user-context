"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI

from graph_context.api.routes import build_router
from graph_context.auth.obo import OboTokenService
from graph_context.auth.token_validation import TokenValidator
from graph_context.config import Settings, get_settings
from graph_context.telemetry import configure_telemetry


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_telemetry(settings)
    docs_url = "/docs" if settings.api_docs_enabled else None
    redoc_url = "/redoc" if settings.api_docs_enabled else None
    application = FastAPI(
        title="Microsoft Graph OBO user-context API",
        version="0.1.0",
        docs_url=docs_url,
        redoc_url=redoc_url,
    )
    try:
        validator = TokenValidator(settings)
        obo = OboTokenService(settings)
        application.include_router(build_router(settings, validator, obo))
    except ValueError:

        @application.get("/health")
        async def health() -> dict[str, str]:
            return {"status": "healthy"}

        @application.get("/ready")
        async def not_ready() -> dict[str, str]:
            return {"status": "not_ready"}

    return application
