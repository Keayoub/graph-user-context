"""Search index provisioning and bounded document synchronization."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any, Protocol

from azure.core.exceptions import HttpResponseError, ServiceRequestError

from graph_context.graph.models import UserRecord

logger = logging.getLogger(__name__)


class IndexClient(Protocol):
    def upload_documents(self, documents: list[dict[str, Any]]) -> list[Any]: ...


def chunks(items: Iterable[dict[str, Any]], size: int) -> Iterable[list[dict[str, Any]]]:
    batch: list[dict[str, Any]] = []
    for item in items:
        batch.append(item)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch


def _failed_results(results: list[Any]) -> int:
    return sum(1 for result in results if getattr(result, "succeeded", True) is False)


def sync_documents(
    client: IndexClient,
    users: Iterable[UserRecord],
    *,
    deleted_ids: Iterable[str] = (),
    batch_size: int = 500,
    max_retries: int = 3,
) -> tuple[int, int, int]:
    synchronized_at = datetime.now(UTC)
    indexed = failed = 0
    documents = (
        user.to_search_document(synchronized_at) | {"@search.action": "mergeOrUpload"}
        for user in users
    )
    for batch in chunks(documents, batch_size):
        results: list[Any] | None = None
        for attempt in range(max_retries + 1):
            try:
                results = client.upload_documents(batch)
                break
            except (HttpResponseError, ServiceRequestError):
                if attempt >= max_retries:
                    raise
                logger.warning("Retrying Search batch attempt=%s", attempt + 1)
        if results is None:
            continue
        batch_failed = _failed_results(results)
        indexed += len(batch) - batch_failed
        failed += batch_failed

    deletion_documents = ({"id": user_id, "@search.action": "delete"} for user_id in deleted_ids)
    deleted = 0
    for batch in chunks(deletion_documents, batch_size):
        results = client.upload_documents(batch)
        batch_failed = _failed_results(results)
        deleted += len(batch) - batch_failed
        failed += batch_failed
    return indexed, deleted, failed


def provision_index(index_client: Any, name: str) -> Any:
    from graph_context.search.schema import organization_index

    return index_client.create_or_update_index(organization_index(name))
