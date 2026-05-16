from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = REPO_ROOT / "docs" / "cloud" / "backend_api.md"


def test_cloud_backend_api_doc_is_explicitly_future_only() -> None:
    assert DOC_PATH.exists()

    content = DOC_PATH.read_text(encoding="utf-8").lower()

    for expected in (
        "future backend api",
        "no backend api is implemented now",
        "only after the local workflow works",
        "local-first",
    ):
        assert expected in content


def test_cloud_backend_api_doc_covers_required_resources() -> None:
    assert DOC_PATH.exists()

    content = DOC_PATH.read_text(encoding="utf-8")

    for endpoint in (
        "POST /v1/uploads",
        "POST /v1/jobs",
        "GET /v1/jobs/{job_id}",
        "GET /v1/jobs/{job_id}/artifacts",
        "GET /v1/artifacts/{artifact_id}",
        "GET /v1/jobs/{job_id}/reports",
        "GET /v1/reports/{report_id}",
        "GET /healthz",
    ):
        assert endpoint in content


def test_cloud_backend_api_doc_maps_local_manifest_to_job_report_concepts() -> None:
    assert DOC_PATH.exists()

    content = DOC_PATH.read_text(encoding="utf-8").lower()

    for expected in (
        "manifest.json",
        "run_id",
        "job_id",
        "created_at_utc",
        "input.kind",
        "input.stored_path",
        "stages",
        "80_reports/run_report.json",
        "artifacts[]",
        "warnings",
        "pre_print_checklist",
    ):
        assert expected in content
