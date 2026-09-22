"""API routes and Graph response normalization."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException

from graph_context.api.dependencies import require_assertion
from graph_context.auth.obo import OboTokenService
from graph_context.auth.token_validation import TokenValidator
from graph_context.config import Settings

logger = logging.getLogger(__name__)
router = APIRouter()


def compact(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if not item:
        return None
    return {
        "id": item.get("id"),
        "displayName": item.get("displayName"),
        "userPrincipalName": item.get("userPrincipalName"),
        "mail": item.get("mail"),
        "jobTitle": item.get("jobTitle"),
        "department": item.get("department"),
        "officeLocation": item.get("officeLocation"),
        "type": (item.get("@odata.type") or "").removeprefix("#microsoft.graph."),
    }


async def collection(client: httpx.AsyncClient, token: str, path: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    next_url: str | None = path
    while next_url:
        response = await client.get(
            next_url
            if next_url.startswith("https://")
            else f"https://graph.microsoft.com/v1.0{next_url}",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        )
        if response.status_code >= 400:
            raise HTTPException(status_code=502, detail="Microsoft Graph request failed")
        payload = response.json()
        items.extend(payload.get("value", []))
        next_url = payload.get("@odata.nextLink")
    return items


async def optional_collection(
    client: httpx.AsyncClient, token: str, path: str, name: str
) -> tuple[list[dict[str, Any]], str | None]:
    try:
        return await collection(client, token, path), None
    except HTTPException as exc:
        logger.warning("Optional Graph section failed section=%s status=%s", name, exc.status_code)
        return [], name


def build_router(settings: Settings, validator: TokenValidator, obo: OboTokenService) -> APIRouter:
    api = APIRouter()

    @api.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "healthy"}

    @api.get("/ready")
    async def ready() -> dict[str, str]:
        try:
            settings.validate_obo()
        except ValueError as exc:
            raise HTTPException(status_code=503, detail="API configuration is incomplete") from exc
        return {"status": "ready"}

    @api.get("/api/user-context")
    async def user_context(assertion: str = Depends(require_assertion)) -> dict[str, Any]:
        claims = await validator.validate(assertion)
        graph_token = await obo.exchange(assertion)
        profile_select = ",".join(
            [
                "id",
                "displayName",
                "givenName",
                "surname",
                "userPrincipalName",
                "mail",
                "jobTitle",
                "department",
                "companyName",
                "officeLocation",
                "businessPhones",
                "mobilePhone",
                "preferredLanguage",
                "usageLocation",
                "streetAddress",
                "city",
                "state",
                "postalCode",
                "country",
            ]
        )
        related_select = "id,displayName,userPrincipalName,mail,jobTitle,department,officeLocation"
        omitted: list[str] = []
        async with httpx.AsyncClient(timeout=httpx.Timeout(settings.request_timeout)) as client:
            profile_task = client.get(
                f"https://graph.microsoft.com/v1.0/me?$select={profile_select}",
                headers={"Authorization": f"Bearer {graph_token}"},
            )
            manager_task = client.get(
                f"https://graph.microsoft.com/v1.0/me/manager/microsoft.graph.user?$select={related_select}",
                headers={"Authorization": f"Bearer {graph_token}"},
            )
            reports_task = optional_collection(
                client,
                graph_token,
                f"/me/directReports/microsoft.graph.user?$select={related_select}&$top=999",
                "directReports",
            )
            memberships_task = optional_collection(
                client,
                graph_token,
                "/me/transitiveMemberOf?$select=id,displayName&$top=999",
                "memberships",
            )
            (
                profile_response,
                manager_response,
                reports_result,
                memberships_result,
            ) = await asyncio.gather(profile_task, manager_task, reports_task, memberships_task)
        if profile_response.status_code >= 400:
            raise HTTPException(status_code=502, detail="Microsoft Graph profile request failed")
        manager = None if manager_response.status_code == 404 else compact(manager_response.json())
        if manager_response.status_code not in {200, 404}:
            omitted.append("manager")
        reports, report_failure = reports_result
        memberships, membership_failure = memberships_result
        omitted.extend(item for item in [report_failure, membership_failure] if item)
        return {
            "user": profile_response.json(),
            "manager": manager,
            "directReports": [compact(item) for item in reports],
            "memberships": [compact(item) for item in memberships],
            "metadata": {
                "retrievedAt": datetime.now(UTC).isoformat(),
                "subject": claims.get("oid") or claims.get("sub"),
                "omittedSections": omitted,
            },
        }

    return api
