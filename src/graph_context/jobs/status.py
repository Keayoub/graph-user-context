"""Durable, redacted synchronization health state."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from graph_context.graph.models import SyncSummary


def write_status(
    path: str,
    *,
    summary: SyncSummary | None = None,
    started_at: datetime,
    finished_at: datetime,
    status: str,
    error: str | None = None,
) -> None:
    payload: dict[str, Any] = {
        "status": status,
        "startedAt": started_at.astimezone(UTC).isoformat(),
        "finishedAt": finished_at.astimezone(UTC).isoformat(),
        "durationSeconds": round((finished_at - started_at).total_seconds(), 3),
        "error": error,
        "summary": summary.model_dump(mode="json", exclude={"delta_link"}) if summary else None,
    }
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def read_status(path: str) -> dict[str, Any] | None:
    destination = Path(path)
    if not destination.exists():
        return None
    try:
        return cast(dict[str, Any], json.loads(destination.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        return None
