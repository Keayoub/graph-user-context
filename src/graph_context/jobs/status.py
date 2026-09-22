"""Durable, redacted synchronization health state."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from azure.core.exceptions import AzureError, ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobClient, ContentSettings

from graph_context.graph.models import SyncSummary


def write_status(
    path: str,
    *,
    summary: SyncSummary | None = None,
    started_at: datetime,
    finished_at: datetime,
    status: str,
    error: str | None = None,
    blob_url: str | None = None,
    managed_identity_client_id: str | None = None,
) -> None:
    payload: dict[str, Any] = {
        "status": status,
        "startedAt": started_at.astimezone(UTC).isoformat(),
        "finishedAt": finished_at.astimezone(UTC).isoformat(),
        "durationSeconds": round((finished_at - started_at).total_seconds(), 3),
        "error": error,
        "summary": summary.model_dump(mode="json", exclude={"delta_link"}) if summary else None,
    }
    content = json.dumps(payload, indent=2)
    if blob_url:
        credential = DefaultAzureCredential(managed_identity_client_id=managed_identity_client_id)
        try:
            BlobClient.from_blob_url(blob_url, credential=credential).upload_blob(
                content,
                overwrite=True,
                content_settings=ContentSettings(content_type="application/json"),
            )
        finally:
            credential.close()
        return
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")


def read_status(
    path: str,
    *,
    blob_url: str | None = None,
    managed_identity_client_id: str | None = None,
) -> dict[str, Any] | None:
    if blob_url:
        credential = DefaultAzureCredential(managed_identity_client_id=managed_identity_client_id)
        try:
            content = (
                BlobClient.from_blob_url(blob_url, credential=credential).download_blob().readall()
            )
            return cast(dict[str, Any], json.loads(content))
        except (AzureError, ResourceNotFoundError, json.JSONDecodeError):
            return None
        finally:
            credential.close()
    destination = Path(path)
    if not destination.exists():
        return None
    try:
        return cast(dict[str, Any], json.loads(destination.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        return None
