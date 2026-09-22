"""Tenant-wide full and incremental synchronization entry points."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from graph_context.auth.app_credentials import build_app_credential
from graph_context.config import Settings, get_settings
from graph_context.graph.client import GraphClient
from graph_context.graph.memberships import build_membership_map
from graph_context.graph.models import SyncSummary, UserRecord
from graph_context.graph.relationships import build_direct_report_map, build_manager_map
from graph_context.graph.users import USER_FIELDS, get_users
from graph_context.jobs.status import write_status
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
    started_at = datetime.now(UTC)
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
        user_ids = {user.id for user in users}
        users_without_manager = sum(user.manager is None for user in enriched)
        users_without_memberships = sum(
            settings.sync_memberships and not user.memberships for user in enriched
        )
        orphaned_direct_reports = sum(
            report.id not in user_ids
            for user in enriched
            for report in user.direct_reports
            if report.id
        )
        summary = SyncSummary(
            users_seen=len(users),
            users_indexed=indexed,
            users_deleted=deleted,
            relationship_failures=relationship_failures,
            membership_failures=membership_failures,
            indexing_failures=indexing_failures,
            graph_requests=graph.requests,
            graph_retries=graph.retries,
            graph_throttles=graph.throttles,
            users_without_manager=users_without_manager,
            users_without_memberships=users_without_memberships,
            orphaned_direct_reports=orphaned_direct_reports,
            delta_link=final_delta,
        )
        logger.info(
            "sync_status=%s users_seen=%s users_indexed=%s users_deleted=%s "
            "graph_retries=%s graph_throttles=%s relationship_failures=%s "
            "membership_failures=%s indexing_failures=%s",
            "succeeded"
            if not (relationship_failures or membership_failures or indexing_failures)
            else "degraded",
            summary.users_seen,
            summary.users_indexed,
            summary.users_deleted,
            summary.graph_retries,
            summary.graph_throttles,
            summary.relationship_failures,
            summary.membership_failures,
            summary.indexing_failures,
        )
        write_status(
            settings.sync_status_path,
            summary=summary,
            started_at=started_at,
            finished_at=datetime.now(UTC),
            status=(
                "succeeded"
                if not (relationship_failures or membership_failures or indexing_failures)
                else "degraded"
            ),
            blob_url=settings.sync_status_blob_url,
            managed_identity_client_id=settings.client_id or None,
        )
        return summary
    except Exception as exc:
        logger.exception("sync_status=failed error_type=%s", type(exc).__name__)
        write_status(
            settings.sync_status_path,
            started_at=started_at,
            finished_at=datetime.now(UTC),
            status="failed",
            error=type(exc).__name__,
            blob_url=settings.sync_status_blob_url,
            managed_identity_client_id=settings.client_id or None,
        )
        raise
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
