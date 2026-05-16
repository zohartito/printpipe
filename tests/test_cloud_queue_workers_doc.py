from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = REPO_ROOT / "docs" / "cloud" / "queue_workers.md"


def test_queue_workers_doc_sketches_future_architecture_scope() -> None:
    assert DOC_PATH.exists()

    content = DOC_PATH.read_text(encoding="utf-8").lower()

    for expected in (
        "future",
        "not implemented now",
        "meshgen",
        "repair",
        "slicing",
        "report generation",
        "idempotency",
        "retries",
        "progress",
        "cancellation",
        "artifact handoff",
        "gpu worker isolation",
    ):
        assert expected in content
