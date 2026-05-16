from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = REPO_ROOT / "docs" / "cloud" / "cost_billing.md"


def _read_doc() -> str:
    assert DOC_PATH.exists()
    return DOC_PATH.read_text(encoding="utf-8").lower()


def test_cloud_cost_billing_doc_sets_v1_boundary_and_cost_drivers() -> None:
    content = _read_doc()

    for expected in (
        "billing not v1",
        "hosted gpu meshgen",
        "storage",
        "slicing",
        "bandwidth",
        "support",
        "failed runs",
    ):
        assert expected in content


def test_cloud_cost_billing_doc_lists_metrics_needed_before_pricing() -> None:
    content = _read_doc()

    for metric in (
        "gpu_seconds",
        "queue_seconds",
        "storage_gb_days",
        "slice_seconds",
        "egress_bytes",
        "support_minutes",
        "failure_category",
    ):
        assert metric in content

    for expected in (
        "collect metrics before pricing",
        "actual cost",
        "estimated cost",
        "no automatic paid retry",
        "do not charge users for platform failures",
    ):
        assert expected in content
