from datetime import UTC, datetime

from graph_context.graph.models import SyncSummary
from graph_context.jobs.status import read_status, write_status


def test_status_round_trip_contains_counts_without_delta_link(tmp_path) -> None:
    path = tmp_path / "status.json"
    write_status(
        str(path),
        summary=SyncSummary(users_seen=4, graph_throttles=2, delta_link="secret-delta-url"),
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
        finished_at=datetime(2026, 1, 1, 0, 0, 2, tzinfo=UTC),
        status="degraded",
    )

    status = read_status(str(path))

    assert status is not None
    assert status["status"] == "degraded"
    assert status["durationSeconds"] == 2.0
    assert status["summary"]["users_seen"] == 4
    assert "delta_link" not in status["summary"]
