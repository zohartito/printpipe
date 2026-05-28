from __future__ import annotations

import json
from pathlib import Path

from printpipe.cli import main
from printpipe.packaging.smoke import (
    build_macos_package_smoke_plan,
    run_macos_package_smoke,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_macos_package_smoke_plan_is_clean_environment_friendly(tmp_path: Path) -> None:
    plan = build_macos_package_smoke_plan(runs_dir=tmp_path / "runs")
    payload = plan.to_dict()

    assert payload["platform"] == "macos"
    assert payload["runs_dir"] == str(tmp_path / "runs")
    assert payload["fixture_source"] == "generated_ascii_stl"
    assert [step["id"] for step in payload["steps"]] == [
        "version",
        "doctor",
        "pipeline",
        "status",
        "open_report",
        "serve",
    ]
    assert "printpipe --version" in payload["steps"][0]["command"]
    assert "printpipe doctor --platform macos --json" in payload["steps"][1]["command"]
    assert "--runs-dir" in payload["steps"][2]["command"]
    json.dumps(payload)


def test_run_macos_package_smoke_creates_bundle_and_report_receipts(tmp_path: Path) -> None:
    result = run_macos_package_smoke(runs_dir=tmp_path / "runs")
    payload = result.to_dict()

    assert payload["platform"] == "macos"
    assert payload["status"] == "ok"
    assert payload["run_root"]
    assert Path(payload["run_root"]).exists()
    assert payload["input_fixture"].endswith("package_smoke_tiny_tetrahedron.stl")

    checks = {check["id"]: check for check in payload["checks"]}
    assert checks["input_fixture"]["status"] == "ok"
    assert checks["pipeline_run"]["status"] == "ok"
    assert checks["reports"]["status"] == "ok"
    assert checks["bundle"]["status"] == "ok"
    assert checks["slice_gate"]["status"] == "manual_required"

    report_paths = checks["reports"]["details"]["paths"]
    assert (Path(payload["run_root"]) / "manifest.json").exists()
    assert any(path.endswith("run_report.json") for path in report_paths)
    assert any(path.endswith(".3mf") for path in checks["bundle"]["details"]["paths"])
    json.dumps(payload)


def test_cli_package_smoke_macos_json_reports_artifacts(
    tmp_path: Path,
    capsys,
) -> None:
    exit_code = main(
        [
            "package-smoke",
            "--platform",
            "macos",
            "--runs-dir",
            str(tmp_path / "runs"),
            "--json",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["platform"] == "macos"
    assert payload["status"] == "ok"
    assert Path(payload["run_root"]).exists()


def test_packaging_doc_names_macos_package_smoke_command() -> None:
    content = (REPO_ROOT / "docs" / "PACKAGING.md").read_text(encoding="utf-8").lower()

    for expected in (
        "printpipe package-smoke --platform macos --runs-dir runs/package-smoke/macos --json",
        "generated ascii stl",
        "manual_required",
        "not a signed or notarized .app",
        "f10",
    ):
        assert expected in content
