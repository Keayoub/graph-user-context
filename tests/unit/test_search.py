from __future__ import annotations

from graph_context.graph.models import UserRecord
from graph_context.search.sync import chunks, sync_documents


def test_chunks_respect_batch_size() -> None:
    assert list(chunks(({"id": str(i)} for i in range(5)), 2)) == [
        [{"id": "0"}, {"id": "1"}],
        [{"id": "2"}, {"id": "3"}],
        [{"id": "4"}],
    ]


class Search:
    def __init__(self) -> None:
        self.batches: list[list[dict[str, object]]] = []

    def upload_documents(self, documents: list[dict[str, object]]) -> list[object]:
        self.batches.append(documents)
        return [type("Result", (), {"succeeded": item["id"] != "bad"})() for item in documents]


def test_indexing_and_deletion_report_partial_failures() -> None:
    client = Search()
    users = [UserRecord(id="good", displayName="Good"), UserRecord(id="bad", displayName="Bad")]
    indexed, deleted, failures = sync_documents(client, users, deleted_ids=["old"], batch_size=1)
    assert indexed == 1
    assert deleted == 1
    assert failures == 1
    assert client.batches[-1][0]["@search.action"] == "delete"
