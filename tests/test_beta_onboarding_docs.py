from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BETA_README = REPO_ROOT / "docs" / "beta" / "README.md"
ONBOARDING_DOC = REPO_ROOT / "docs" / "beta" / "onboarding.md"


def _read(path: Path) -> str:
    assert path.exists()
    return path.read_text(encoding="utf-8").lower()


def test_beta_readme_points_trusted_users_to_onboarding() -> None:
    content = _read(BETA_README)

    for expected in (
        "# printpipe beta",
        "3-5 trusted users",
        "local-first",
        "onboarding.md",
        "not a finished print-ready pipeline",
    ):
        assert expected in content


def test_onboarding_doc_lists_required_setup_and_run_commands() -> None:
    content = _read(ONBOARDING_DOC)

    for expected in (
        "python -m venv .venv",
        "source .venv/bin/activate",
        'python -m pip install -e ".[dev]"',
        "printpipe --version",
        "printpipe doctor",
        "printpipe doctor --json",
        "tests/fixtures/objects/existing_stl_pipeline/tiny_tetrahedron.stl",
        "printpipe run tests/fixtures/objects/existing_stl_pipeline/tiny_tetrahedron.stl --runs-dir runs",
        "printpipe status runs/<run-id>",
        "printpipe open-report runs/<run-id>",
    ):
        assert expected in content


def test_onboarding_doc_contains_safety_and_current_limits_language() -> None:
    content = _read(ONBOARDING_DOC)

    for expected in (
        "do not start an unattended print from printpipe outputs",
        "has not been physically validated",
        "current skeleton pipeline",
        "not print-ready",
        "do not print footwear for wear",
        "do not print food-contact parts",
        "do not print load-bearing parts",
        "do not print medical or safety-critical parts",
        "do not print parts for children or pets",
    ):
        assert expected in content


def test_onboarding_doc_covers_local_first_privacy_and_feedback_artifacts() -> None:
    content = _read(ONBOARDING_DOC)

    for expected in (
        "local-first",
        "no cloud upload is required for this beta path",
        "do not share private inputs",
        "remove faces, addresses, documents, and location metadata",
        "manifest.json",
        "10_frames/contact_sheet_manifest.json",
        "80_reports/run_report.json",
        "80_reports/run_report.md",
        "80_reports/run_report.html",
        "60_bundle/",
        "slice log or slice report",
        "printpipe doctor --json",
        "what you expected",
        "what happened",
        "whether you opened the report",
    ):
        assert expected in content


def test_onboarding_doc_names_physical_evidence_packet_requirements() -> None:
    content = _read(ONBOARDING_DOC)

    for expected in (
        "physical evidence packet",
        "operator",
        "print status",
        "photo artifact",
        "filament drying",
        "layer bonding",
        "flex recovery",
        "first layer",
        "adhesion",
        "warping",
        "stringing",
    ):
        assert expected in content
