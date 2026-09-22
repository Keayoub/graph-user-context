"""Bounded direct-report traversal and reverse manager-map construction."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Iterable
from typing import Any, TypeVar, cast

from graph_context.graph.client import GraphClient, GraphRequestError
from graph_context.graph.models import DirectoryObject, UserRecord
from graph_context.graph.users import RELATED_FIELDS, normalize_user_items

logger = logging.getLogger(__name__)
T = TypeVar("T")


async def bounded_map(
    values: Iterable[T], worker: Callable[[T], Awaitable[object]], concurrency: int
) -> list[object | Exception]:
    queue: asyncio.Queue[tuple[int, T] | None] = asyncio.Queue()
    indexed = list(values)
    results: list[object | Exception] = [
        RuntimeError("worker did not produce a result") for _ in indexed
    ]
    for item in enumerate(indexed):
        queue.put_nowait(item)

    async def consume() -> None:
        while True:
            item = await queue.get()
            if item is None:
                queue.task_done()
                return
            index, value = item
            try:
                results[index] = await worker(value)
            except Exception as exc:
                results[index] = exc
            finally:
                queue.task_done()

    workers = [asyncio.create_task(consume()) for _ in range(min(concurrency, len(indexed)))]
    for _ in workers:
        queue.put_nowait(None)
    await queue.join()
    await asyncio.gather(*workers)
    return results


async def direct_reports(graph: GraphClient, user: UserRecord) -> list[dict[str, object]]:
    path = (
        f"/users/{user.id}/directReports/microsoft.graph.user"
        f"?$select={','.join(RELATED_FIELDS)}&$top=999"
    )
    return normalize_user_items(await graph.all_items(path))


async def build_manager_map(
    graph: GraphClient, users: list[UserRecord], concurrency: int
) -> tuple[dict[str, DirectoryObject], int]:
    results = await bounded_map(users, lambda user: direct_reports(graph, user), concurrency)
    manager_map: dict[str, DirectoryObject] = {}
    failures = 0
    for manager, result in zip(users, results, strict=True):
        if isinstance(result, Exception):
            failures += 1
            if isinstance(result, GraphRequestError) and result.status_code in {401, 403, 404}:
                logger.warning("Skipping inaccessible direct reports for user_id=%s", manager.id)
            else:
                logger.exception(
                    "Direct-report lookup failed user_id=%s", manager.id, exc_info=result
                )
            continue
        compact = DirectoryObject.model_validate(
            {
                "id": manager.id,
                "displayName": manager.display_name,
                "userPrincipalName": manager.user_principal_name,
                "mail": manager.mail,
                "jobTitle": manager.job_title,
                "department": manager.department,
                "officeLocation": manager.office_location,
            }
        )
        for report in cast(list[dict[str, Any]], result):
            report_id = report.get("id")
            if report_id:
                manager_map[str(report_id)] = compact
    return manager_map, failures


async def build_direct_report_map(
    graph: GraphClient, users: list[UserRecord], concurrency: int
) -> tuple[dict[str, list[DirectoryObject]], int]:
    results = await bounded_map(users, lambda user: direct_reports(graph, user), concurrency)
    report_map: dict[str, list[DirectoryObject]] = {}
    failures = 0
    for user, result in zip(users, results, strict=True):
        if isinstance(result, Exception):
            failures += 1
            continue
        report_map[user.id] = [
            DirectoryObject.model_validate(item) for item in cast(list[dict[str, Any]], result)
        ]
    return report_map, failures
