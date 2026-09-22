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


async def build_membership_map(
    graph: GraphClient, users: list[UserRecord], settings: Settings
) -> tuple[dict[str, list[Membership]], int]:
    if not settings.sync_memberships:
        return {}, 0
    results = await bounded_map(
        users,
        lambda user: get_user_memberships(graph, user.id),
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
        membership_map[user.id] = cast(list[Membership], result)
    return membership_map, failures
