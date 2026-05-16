from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = REPO_ROOT / "docs" / "cloud" / "local_power_user.md"
README_PATH = REPO_ROOT / "docs" / "cloud" / "README.md"


def test_local_power_user_doc_preserves_local_app_boundary() -> None:
    assert DOC_PATH.exists()

    content = DOC_PATH.read_text(encoding="utf-8").lower()

    for expected in (
        "# local power-user plan",
        "local app remains the power-user version",
        "even if cloud exists later",
        "cli parity",
        "offline/private runs",
        "local bambu studio integration",
        "local artifacts",
        "run folders",
        "export from local to cloud",
        "import from cloud to local",
    ):
        assert expected in content


def test_cloud_readme_links_wave_10_docs() -> None:
    assert README_PATH.exists()

    content = README_PATH.read_text(encoding="utf-8").lower()

    for expected in (
        "# cloud planning docs",
        "wave 10",
        "backend_api.md",
        "queue_workers.md",
        "storage_auth.md",
        "cost_billing.md",
        "meshgen_decision.md",
        "local_power_user.md",
    ):
        assert expected in content
