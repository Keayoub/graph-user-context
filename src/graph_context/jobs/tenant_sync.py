"""Tenant-wide full and incremental synchronization entry points."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from graph_context.auth.app_credentials import build_app_credential
from graph_context.config import Settings, get_settings
from graph_context.graph.client import GraphClient
from graph_context.graph.memberships import build_membership_map
from graph_context.graph.models import SyncSummary, UserRecord
from graph_context.graph.relationships import build_direct_report_map, build_manager_map
from graph_context.graph.users import USER_FIELDS, get_users
from graph_context.search.client import build_search_client
from graph_context.search.sync import sync_documents

logger = logging.getLogger(__name__)


def _read_delta(path: Path) -> str | None:
    return path.read_text(encoding="utf-8").strip() if path.exists() else None


def _write_delta(path: Path, value: str | None) -> None:
    if value:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8")


async def synchronize(settings: Settings, *, full: bool = False) -> SyncSummary:
    settings.validate_sync()
    credential = build_app_credential(settings)
    graph = GraphClient(
        credential,
        base_url=settings.graph_base_url,
        concurrency=settings.concurrency,
        max_retries=settings.max_retries,
        timeout=settings.request_timeout,
    )
    try:
        delta_path = Path(settings.delta_link_path)
        delta_url = None if full else _read_delta(delta_path)
        if delta_url:
            changed, final_delta = await graph.delta(delta_url, USER_FIELDS)
            deleted_ids = [
                str(item["id"]) for item in changed if item.get("@removed") and item.get("id")
            ]
            users = [
                UserRecord.model_validate(item)
                for item in changed
                if not item.get("@removed") and item.get("id")
            ]
        else:
            users = await get_users(graph)
            final_delta = None
            deleted_ids = []

        manager_map, relationship_failures = await build_manager_map(
            graph, users, settings.concurrency
        )
        report_map, _ = await build_direct_report_map(graph, users, settings.concurrency)
        membership_map, membership_failures = await build_membership_map(graph, users, settings)
        enriched: list[UserRecord] = []
        for user in users:
            enriched.append(
                user.model_copy(
                    update={
                        "manager": manager_map.get(user.id),
                        "directReports": report_map.get(user.id, []),
                        "memberships": membership_map.get(user.id, []),
                    }
                )
            )
        if settings.search_endpoint:
            search = build_search_client(settings)
            indexed, deleted, indexing_failures = sync_documents(
                search,
                enriched,
                deleted_ids=deleted_ids,
                batch_size=settings.batch_size,
                max_retries=settings.max_retries,
            )
        else:
            indexed, deleted, indexing_failures = 0, 0, 0
        _write_delta(delta_path, final_delta)
        summary = SyncSummary(
            users_seen=len(users),
            users_indexed=indexed,
            users_deleted=deleted,
            relationship_failures=relationship_failures,
            membership_failures=membership_failures,
            indexing_failures=indexing_failures,
            delta_link=final_delta,
        )
        logger.info(
            "Tenant synchronization complete: %s", summary.model_dump(exclude={"delta_link"})
        )
        return summary
    finally:
        await graph.close()
        await credential.close()


def main() -> None:
    logging.basicConfig(
        level=get_settings().log_level, format="%(asctime)s %(levelname)s %(message)s"
    )
    import argparse

    parser = argparse.ArgumentParser(
        description="Synchronize Entra organizational context to Azure AI Search"
    )
    parser.add_argument("--full", action="store_true", help="Ignore the saved delta link")
    args = parser.parse_args()
    summary = asyncio.run(synchronize(get_settings(), full=args.full))
    print(json.dumps(summary.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    main()
