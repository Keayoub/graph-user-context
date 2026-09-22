"""Membership retrieval with support for limited-information objects."""

from __future__ import annotations

import logging
from typing import cast

from graph_context.config import Settings
from graph_context.graph.client import GraphClient, GraphRequestError
from graph_context.graph.models import Membership, UserRecord
from graph_context.graph.relationships import bounded_map
from graph_context.graph.users import normalize_user_items

logger = logging.getLogger(__name__)


async def get_user_memberships(graph: GraphClient, user_id: str) -> list[Membership]:
    path = f"/users/{user_id}/transitiveMemberOf?$select=id,displayName&$top=999"
    items = normalize_user_items(await graph.all_items(path))
    return [Membership.model_validate(item) for item in items]


async def get_user_membership_type(
    graph: GraphClient, user_id: str, object_type: str
) -> list[Membership]:
    path = (
        f"/users/{user_id}/transitiveMemberOf/microsoft.graph.{object_type}"
        "?$select=id,displayName&$top=999"
    )
    items = normalize_user_items(await graph.all_items(path))
    return [Membership.model_validate(item) for item in items]


async def get_user_memberships_with_options(
    graph: GraphClient, user_id: str, settings: Settings
) -> tuple[list[Membership], int]:
    results = await get_user_memberships(graph, user_id)
    failures = 0
    optional_types = []
    if settings.sync_roles:
        optional_types.append("directoryRole")
    if settings.sync_administrative_units:
        optional_types.append("administrativeUnit")

    optional_results = await bounded_map(
        optional_types,
        lambda object_type: get_user_membership_type(graph, user_id, object_type),
        max(1, min(settings.concurrency, len(optional_types))),
    )
    for object_type, result in zip(optional_types, optional_results, strict=True):
        if isinstance(result, Exception):
            failures += 1
            if isinstance(result, GraphRequestError) and result.status_code in {401, 403, 404}:
                logger.warning(
                    "Optional membership type unavailable user_id=%s type=%s status=%s",
                    user_id,
                    object_type,
                    result.status_code,
                )
            else:
                logger.exception(
                    "Optional membership type lookup failed user_id=%s type=%s",
                    user_id,
                    object_type,
                    exc_info=result,
                )
            continue
        results.extend(cast(list[Membership], result))

    unique: dict[tuple[str | None, str | None], Membership] = {}
    for membership in results:
        key = (membership.id, membership.object_type)
        unique[key] = membership
    return list(unique.values()), failures


async def build_membership_map(
    graph: GraphClient, users: list[UserRecord], settings: Settings
) -> tuple[dict[str, list[Membership]], int]:
    if not settings.sync_memberships:
        return {}, 0
    results = await bounded_map(
        users,
        lambda user: get_user_memberships_with_options(graph, user.id, settings),
        settings.concurrency,
    )
    membership_map: dict[str, list[Membership]] = {}
    failures = 0
    for user, result in zip(users, results, strict=True):
        if isinstance(result, Exception):
            failures += 1
            if isinstance(result, GraphRequestError) and result.status_code in {401, 403, 404}:
                logger.warning(
                    "Memberships unavailable user_id=%s status=%s", user.id, result.status_code
                )
            else:
                logger.exception("Membership lookup failed user_id=%s", user.id, exc_info=result)
            continue
        memberships, optional_failures = cast(tuple[list[Membership], int], result)
        membership_map[user.id] = memberships
        failures += optional_failures
    return membership_map, failures
