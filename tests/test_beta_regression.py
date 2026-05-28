from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from printpipe.beta.regression import (
    ExpectedOutcome,
    RegressionCase,
    RegressionManifest,
    build_failure_regression_status,
    case_from_run,
    load_regression_manifest,
    render_command,
    run_regression_manifest,
    validate_regression_manifest,
    write_regression_manifest,
)
from printpipe.cli import main


def _case_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "case_id": "slipper-non-manifold",
        "source_run_id": "20260516-101112-slipper",
        "fixture_path": "tests/fixtures/regression/slipper.stl",
        "command": ["printpipe", "run", "tests/fixtures/regression/slipper.stl"],
        "expected": "failure",
        "notes": "Captured from a failed dogfood run.",
    }
    payload.update(overrides)
    return payload


def test_validate_regression_manifest_reports_shape_errors() -> None:
    payload = {
        "schema_version": 2,
        "cases": [
            _case_payload(),
            _case_payload(case_id=""),
            _case_payload(expected="retry"),
        ],
    }

    assert validate_regression_manifest(payload) == (
        "schema_version must be 1",
        "cases[1].case_id must be a non-empty string",
        "cases[2].case_id duplicates cases[0].case_id: slipper-non-manifold",
        "cases[2].expected must be 'failure' or 'success'",
    )


def test_regression_manifest_json_round_trip(tmp_path: Path) -> None:
    manifest = RegressionManifest(
        cases=(
            RegressionCase(
                case_id="slipper-non-manifold",
                source_run_id="20260516-101112-slipper",
                fixture_path=Path("tests/fixtures/regression/slipper.stl"),
                command=("printpipe", "run", "tests/fixtures/regression/slipper.stl"),
                expected=ExpectedOutcome.FAILURE,
                notes="Captured from a failed dogfood run.",
            ),
        )
    )
    manifest_path = tmp_path / "regression_manifest.json"

    written_path = write_regression_manifest(manifest, manifest_path)
    loaded = load_regression_manifest(written_path)

    assert written_path == manifest_path
    assert loaded == manifest
    assert manifest_path.read_text(encoding="utf-8").endswith("\n")
    assert json.loads(manifest_path.read_text(encoding="utf-8")) == {
        "schema_version": 1,
        "cases": [
            {
                "case_id": "slipper-non-manifold",
                "source_run_id": "20260516-101112-slipper",
                "fixture_path": "tests/fixtures/regression/slipper.stl",
                "command": ["printpipe", "run", "tests/fixtures/regression/slipper.stl"],
                "expected": "failure",
                "notes": "Captured from a failed dogfood run.",
            }
        ],
    }


def test_write_regression_manifest_rejects_invalid_cases(tmp_path: Path) -> None:
    manifest = RegressionManifest(
        cases=(
            RegressionCase(
                case_id="",
                source_run_id="run-001",
                fixture_path=Path("tests/fixtures/regression/slipper.stl"),
                command=("printpipe", "run", "tests/fixtures/regression/slipper.stl"),
            ),
        )
    )

    with pytest.raises(ValueError, match="case_id"):
        write_regression_manifest(manifest, tmp_path / "regression_manifest.json")


def test_render_command_is_stable_and_shell_safe() -> None:
    command = (
        "printpipe",
        "run",
        Path("tests/fixtures/regression/slipper bad mesh.stl"),
        "--printer",
        "Bambu Lab P2S 0.4 nozzle",
    )

    assert render_command(command) == (
        "printpipe run 'tests/fixtures/regression/slipper bad mesh.stl' "
        "--printer 'Bambu Lab P2S 0.4 nozzle'"
    )
    assert RegressionCase(
        case_id="slipper-bad-mesh",
        source_run_id="run-001",
        fixture_path=Path("tests/fixtures/regression/slipper bad mesh.stl"),
        command=command,
    ).rendered_command == render_command(command)


def test_case_from_run_uses_run_manifest_defaults(tmp_path: Path) -> None:
    run_root = tmp_path / "runs" / "20260516-101112-slipper"
    input_dir = run_root / "00_input"
    input_dir.mkdir(parents=True)
    (input_dir / "slipper.stl").write_text("solid slipper\nendsolid slipper\n", encoding="utf-8")
    (run_root / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "run_id": "20260516-101112-slipper",
                "input": {"stored_path": "00_input/slipper.stl"},
            }
        ),
        encoding="utf-8",
    )

    case = case_from_run(
        run_root,
        command=("printpipe", "run", input_dir / "slipper.stl"),
        notes="Captured from slice failure.",
    )

    assert case == RegressionCase(
        case_id="regression-20260516-101112-slipper",
        source_run_id="20260516-101112-slipper",
        fixture_path=input_dir / "slipper.stl",
        command=("printpipe", "run", str(input_dir / "slipper.stl")),
        expected=ExpectedOutcome.FAILURE,
        notes="Captured from slice failure.",
    )


def test_run_regression_manifest_marks_expected_outcomes(tmp_path: Path) -> None:
    manifest_path = tmp_path / "regression_manifest.json"
    manifest = RegressionManifest(
        cases=(
            RegressionCase(
                case_id="known-failure",
                source_run_id="run-failed",
                fixture_path=Path("fixtures/bad.stl"),
                command=(sys.executable, "-c", "raise SystemExit(2)"),
                expected=ExpectedOutcome.FAILURE,
                notes="Known failure should stay red until fixed.",
            ),
            RegressionCase(
                case_id="known-success",
                source_run_id="run-fixed",
                fixture_path=Path("fixtures/good.stl"),
                command=(sys.executable, "-c", "print('ok')"),
                expected=ExpectedOutcome.SUCCESS,
                notes="Fixed case should stay green.",
            ),
        )
    )
    write_regression_manifest(manifest, manifest_path)

    result = run_regression_manifest(manifest_path)

    assert result["overall_status"] == "passed"
    assert result["case_count"] == 2
    assert result["passed_count"] == 2
    assert result["failed_count"] == 0
    assert result["cases"][0]["case_id"] == "known-failure"
    assert result["cases"][0]["actual"] == "failure"
    assert result["cases"][0]["status"] == "passed"
    assert result["cases"][0]["exit_code"] == 2
    assert result["cases"][1]["case_id"] == "known-success"
    assert result["cases"][1]["actual"] == "success"
    assert result["cases"][1]["status"] == "passed"
    assert result["cases"][1]["stdout"] == "ok\n"


def test_run_regression_manifest_flags_unexpected_passes_and_failures(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "regression_manifest.json"
    manifest = RegressionManifest(
        cases=(
            RegressionCase(
                case_id="unexpected-pass",
                source_run_id="run-failed",
                fixture_path=Path("fixtures/bad.stl"),
                command=(sys.executable, "-c", "raise SystemExit(0)"),
                expected=ExpectedOutcome.FAILURE,
                notes="This failure unexpectedly disappeared.",
            ),
            RegressionCase(
                case_id="unexpected-failure",
                source_run_id="run-fixed",
                fixture_path=Path("fixtures/good.stl"),
                command=(sys.executable, "-c", "raise SystemExit(3)"),
                expected=ExpectedOutcome.SUCCESS,
                notes="This fixed case regressed.",
            ),
        )
    )
    write_regression_manifest(manifest, manifest_path)

    result = run_regression_manifest(manifest_path)

    assert result["overall_status"] == "failed"
    assert result["passed_count"] == 0
    assert result["failed_count"] == 2
    assert result["cases"][0]["status"] == "failed"
    assert result["cases"][0]["actual"] == "success"
    assert result["cases"][0]["message"] == "expected failure but command succeeded"
    assert result["cases"][1]["status"] == "failed"
    assert result["cases"][1]["actual"] == "failure"
    assert result["cases"][1]["message"] == "expected success but command failed"


def test_cli_run_regressions_prints_json_and_strict_exit_code(
    tmp_path: Path,
    capsys,
) -> None:
    manifest_path = tmp_path / "regression_manifest.json"
    manifest = RegressionManifest(
        cases=(
            RegressionCase(
                case_id="unexpected-pass",
                source_run_id="run-failed",
                fixture_path=Path("fixtures/bad.stl"),
                command=(sys.executable, "-c", "raise SystemExit(0)"),
                expected=ExpectedOutcome.FAILURE,
                notes="This failure unexpectedly disappeared.",
            ),
        )
    )
    write_regression_manifest(manifest, manifest_path)

    exit_code = main(["run-regressions", str(manifest_path), "--json", "--strict"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert payload["overall_status"] == "failed"
    assert payload["cases"][0]["case_id"] == "unexpected-pass"


def test_failure_regression_status_requires_manifest_cases_for_failure_packets(
    tmp_path: Path,
) -> None:
    from printpipe.beta.failures import build_failure_report, write_failure_report_files

    runs_dir = tmp_path / "runs"
    run_root = runs_dir / "dogfood" / "run-flat-bracket-failed"
    run_root.mkdir(parents=True)
    write_failure_report_files(
        run_root=run_root,
        report=build_failure_report(
            run_id="run-flat-bracket-failed",
            input_type="existing_stl",
            material="Bambu PETG Basic",
            printer="Bambu Lab P2S",
            failed_stage="slice",
            symptoms=("Plate was empty/off-bed before rotation fix.",),
            artifacts=(),
            reproduction_command="python -m pytest tests/test_pipeline_existing_mesh.py",
            physical_print_status="not_printed",
        ),
    )

    missing = build_failure_regression_status(
        runs_dir,
        regression_manifest_path=tmp_path / "missing.json",
    )

    assert missing["overall_status"] == "missing_manifest"
    assert missing["failure_report_count"] == 1
    assert missing["covered_failure_count"] == 0
    assert missing["missing_regression_source_run_ids"] == ["run-flat-bracket-failed"]

    manifest_path = tmp_path / "regressions" / "dogfood.json"
    manifest_path.parent.mkdir(parents=True)
    write_regression_manifest(
        RegressionManifest(
            cases=(
                RegressionCase(
                    case_id="flat-bracket-orientation",
                    source_run_id="run-flat-bracket-failed",
                    fixture_path=Path("tests/fixtures/objects/flat_bracket/flat_bracket.stl"),
                    command=(
                        sys.executable,
                        "-m",
                        "pytest",
                        "tests/test_pipeline_existing_mesh.py::test_existing_mesh_pipeline_applies_bed_fit_rotation_before_bundle",
                    ),
                    expected=ExpectedOutcome.SUCCESS,
                    notes="Guards the fixed dogfood failure.",
                ),
            )
        ),
        manifest_path,
    )

    covered = build_failure_regression_status(
        runs_dir,
        regression_manifest_path=manifest_path,
    )

    assert covered["overall_status"] == "passed"
    assert covered["failure_report_count"] == 1
    assert covered["covered_failure_count"] == 1
    assert covered["missing_regression_source_run_ids"] == []


def test_cli_failure_regression_status_reports_coverage(
    tmp_path: Path,
    capsys,
) -> None:
    from printpipe.beta.failures import build_failure_report, write_failure_report_files

    runs_dir = tmp_path / "runs"
    run_root = runs_dir / "run-cup-vase-failed"
    run_root.mkdir(parents=True)
    write_failure_report_files(
        run_root=run_root,
        report=build_failure_report(
            run_id="run-cup-vase-failed",
            input_type="existing_stl",
            material="Bambu PLA Basic",
            printer="Bambu Lab P2S",
            failed_stage="mesh_repair",
            symptoms=("Open rim remained non-watertight.",),
            artifacts=(),
            reproduction_command="python -m pytest tests/test_mesh_repair.py",
            physical_print_status="not_printed",
        ),
    )
    manifest_path = tmp_path / "regressions" / "dogfood.json"
    manifest_path.parent.mkdir(parents=True)
    write_regression_manifest(
        RegressionManifest(
            cases=(
                RegressionCase(
                    case_id="cup-vase-repair",
                    source_run_id="run-cup-vase-failed",
                    fixture_path=Path("tests/fixtures/objects/cup_vase/cup_vase_open_frustum.stl"),
                    command=(sys.executable, "-m", "pytest", "tests/test_mesh_repair.py"),
                    expected=ExpectedOutcome.SUCCESS,
                    notes="Guards repaired open-rim behavior.",
                ),
            )
        ),
        manifest_path,
    )

    exit_code = main(
        [
            "failure-regression-status",
            "--runs-dir",
            str(runs_dir),
            "--regression-manifest",
            str(manifest_path),
            "--json",
            "--strict",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["overall_status"] == "passed"
    assert payload["covered_failure_count"] == 1
