from __future__ import annotations

import json
from pathlib import Path

from printpipe.cli import main
from printpipe.packaging.smoke import (
    build_macos_package_smoke_plan,
    build_windows_package_smoke_plan,
    run_macos_package_smoke,
    run_windows_package_smoke,
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


def test_windows_package_smoke_plan_is_powershell_friendly(tmp_path: Path) -> None:
    plan = build_windows_package_smoke_plan(runs_dir=tmp_path / "runs")
    payload = plan.to_dict()

    assert payload["platform"] == "windows"
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
    assert "printpipe doctor --platform windows --json" in payload["steps"][1]["command"]
    assert "/users/" not in payload["steps"][2]["command"].lower()
    assert "printpipe package-smoke --platform windows" in payload["recommended_command"]
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
    assert "separate slice gate" in checks["slice_gate"]["details"]["reason"]
    assert "segfault" not in checks["slice_gate"]["details"]["reason"].lower()

    report_paths = checks["reports"]["details"]["paths"]
    assert (Path(payload["run_root"]) / "manifest.json").exists()
    assert any(path.endswith("run_report.json") for path in report_paths)
    assert any(path.endswith(".3mf") for path in checks["bundle"]["details"]["paths"])
    json.dumps(payload)


def test_run_windows_package_smoke_requires_real_windows_runtime_on_macos(
    tmp_path: Path,
) -> None:
    result = run_windows_package_smoke(
        runs_dir=tmp_path / "runs",
        platform_name="darwin",
    )
    payload = result.to_dict()

    assert payload["platform"] == "windows"
    assert payload["status"] == "manual_required"
    assert payload["run_root"] == ""
    checks = {check["id"]: check for check in payload["checks"]}
    assert checks["windows_runtime"]["status"] == "manual_required"
    assert "run this command on Windows" in checks["windows_runtime"]["details"]["reason"]
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


def test_cli_package_smoke_windows_plan_json(capsys) -> None:
    exit_code = main(["package-smoke", "--platform", "windows", "--plan", "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["platform"] == "windows"
    assert payload["runs_dir"] == "runs/package-smoke/windows"
    assert payload["recommended_command"].startswith("printpipe package-smoke --platform windows")
    assert "/users/" not in json.dumps(payload).lower()


def test_packaging_doc_names_macos_package_smoke_command() -> None:
    content = (REPO_ROOT / "docs" / "PACKAGING.md").read_text(encoding="utf-8").lower()

    for expected in (
        "printpipe package-smoke --platform macos --runs-dir runs/package-smoke/macos --json",
        "printpipe package-smoke --platform windows --runs-dir runs/package-smoke/windows --json",
        "generated ascii stl",
        "manual_required",
        "run this command on windows",
        "printpipe build-zipapp --output dist/printpipe.pyz --json",
        "python dist/printpipe.pyz --version",
        "printpipe build-windows-portable --output dist/printpipe-windows-portable.zip --json",
        "printpipe/printpipe.cmd",
        "printpipe/printpipe.ps1",
        "printpipe/install-start-menu.ps1",
        "printpipe/uninstall-start-menu.ps1",
        "printpipe/install-file-associations.ps1",
        "printpipe/uninstall-file-associations.ps1",
        "skips existing handlers unless",
        "printpipe build-macos-app --output dist/printpipe.app --json",
        "printpipe build-macos-app --output dist/printpipe.app --adhoc-sign --json",
        "codesign --verify --deep --strict dist/printpipe.app",
        "printpipe build-macos-dmg --output dist/printpipe.dmg --adhoc-sign --json",
        "hdiutil imageinfo dist/printpipe.dmg",
        "printpipe_app_dry_run=1 dist/printpipe.app/contents/macos/printpipe",
        "printpipe_app_dry_run=1 dist/printpipe.app/contents/macos/printpipe path/to/input.stl",
        "cfbundledocumenttypes",
        "contents/macos/printpipe --version",
        "windows zipapp smoke evidence",
        "printpipe-zipapp",
        "not a signed or notarized .app",
        "f10",
        "f11",
    ):
        assert expected in content
