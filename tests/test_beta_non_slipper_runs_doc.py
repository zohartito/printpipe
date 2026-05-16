from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = REPO_ROOT / "docs" / "beta" / "non_slipper_beta_runs.md"


def test_non_slipper_beta_runs_doc_covers_required_objects_commands_and_limits() -> None:
    assert DOC_PATH.exists()

    content = DOC_PATH.read_text(encoding="utf-8")
    lower_content = content.lower()

    for expected in (
        "figurine",
        "cup/vase",
        "flat bracket",
        "decorative organic",
        "existing stl",
    ):
        assert expected in lower_content

    for command in (
        "printpipe run tests/fixtures/objects/figurine/simple_figurine_ascii.stl --runs-dir runs/beta/non-slipper",
        "printpipe run tests/fixtures/objects/cup_vase/cup_vase_open_frustum.stl --runs-dir runs/beta/non-slipper",
        "printpipe run tests/fixtures/objects/flat_bracket/flat_bracket.stl --runs-dir runs/beta/non-slipper",
        "printpipe run tests/fixtures/objects/decorative_organic/asymmetric_leaf_shell.stl --runs-dir runs/beta/non-slipper",
        "printpipe run tests/fixtures/objects/existing_stl_pipeline/tiny_tetrahedron.stl --runs-dir runs/beta/non-slipper",
        ".venv/bin/python -m pytest tests/test_existing_stl_pipeline_bundle.py",
    ):
        assert command in content

    for artifact in (
        "manifest.json",
        "00_input/",
        "10_frames/",
        "80_reports/run_report.json",
        "80_reports/run_report.md",
        "80_reports/run_report.html",
        "60_bundle/",
    ):
        assert artifact in content

    for honesty_phrase in (
        "not a substitute for physical printing",
        "does not prove printability",
        "physical printing required",
    ):
        assert honesty_phrase in lower_content
