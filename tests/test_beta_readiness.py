from __future__ import annotations

import sys
from pathlib import Path

from printpipe.beta.readiness import build_beta_readiness_report
from printpipe.beta.regression import (
    ExpectedOutcome,
    RegressionCase,
    RegressionManifest,
    write_regression_manifest,
)


def test_beta_readiness_report_blocks_on_missing_physical_and_signing(
    tmp_path: Path,
) -> None:
    report = build_beta_readiness_report(
        tmp_path / "runs",
        environment_report={
            "platform": {"raw": "darwin", "normalized": "macos"},
            "dependencies": [{"id": "python", "status": "ok"}],
            "bambu_studio": {"installed_count": 1},
            "bambu_profiles": {"candidate_count": 1},
            "filesystem": {"checks": [{"status": "ok"}]},
            "system": {
                "signing": {
                    "status": "missing_identities",
                    "missing_tools": [],
                    "missing_identities": ["Developer ID Application"],
                },
            },
        },
    )

    gates = {gate["id"]: gate for gate in report["gates"]}
    assert report["overall_status"] == "action_required"
    assert gates["physical_validation"]["status"] == "action_required"
    assert gates["trusted_user_beta"]["status"] == "action_required"
    assert gates["signing"]["status"] == "action_required"
    assert "PLA, PETG, and TPU" in gates["physical_validation"]["action"]
    assert "3 trusted users" in gates["trusted_user_beta"]["action"]
    assert "Developer ID Application" in gates["signing"]["detail"]


def test_beta_readiness_report_passes_when_all_gates_are_ready(tmp_path: Path) -> None:
    physical_status = {
        "overall_status": "passed",
        "required_families": ["pla", "petg", "tpu"],
        "family_status": {
            "pla": {"status": "passed"},
            "petg": {"status": "passed"},
            "tpu": {"status": "passed"},
        },
    }
    environment_report = {
        "platform": {"raw": "darwin", "normalized": "macos"},
        "dependencies": [{"id": "python", "status": "ok"}],
        "bambu_studio": {"installed_count": 1},
        "bambu_profiles": {"candidate_count": 1},
        "filesystem": {"checks": [{"status": "ok"}]},
        "system": {"signing": {"status": "ready", "missing_tools": [], "missing_identities": []}},
    }

    report = build_beta_readiness_report(
        tmp_path / "runs",
        physical_status=physical_status,
        trusted_feedback_status=_passed_trusted_feedback_status(),
        environment_report=environment_report,
    )

    assert report["overall_status"] == "ready"
    assert all(
        gate["status"] in {"ready", "not_applicable"}
        for gate in report["gates"]
    )


def test_beta_readiness_report_marks_missing_regression_manifest_not_applicable(
    tmp_path: Path,
) -> None:
    report = build_beta_readiness_report(
        tmp_path / "runs",
        physical_status=_passed_physical_status(),
        trusted_feedback_status=_passed_trusted_feedback_status(),
        environment_report=_ready_environment_report(),
    )

    gates = {gate["id"]: gate for gate in report["gates"]}
    regression_gate = gates["beta_regressions"]

    assert report["overall_status"] == "ready"
    assert regression_gate["status"] == "not_applicable"
    assert "No beta regression manifest configured" in regression_gate["detail"]
    assert report["regression_status"]["overall_status"] == "not_configured"


def test_beta_readiness_report_blocks_on_missing_trusted_user_feedback(
    tmp_path: Path,
) -> None:
    report = build_beta_readiness_report(
        tmp_path / "runs",
        physical_status=_passed_physical_status(),
        environment_report=_ready_environment_report(),
    )

    gates = {gate["id"]: gate for gate in report["gates"]}
    trusted_gate = gates["trusted_user_beta"]

    assert report["overall_status"] == "action_required"
    assert trusted_gate["status"] == "action_required"
    assert "0 / 3 trusted users" in trusted_gate["detail"]
    assert "record-beta-feedback" in trusted_gate["action"]


def test_beta_readiness_report_blocks_on_regression_manifest_drift(
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
                notes="Known failure unexpectedly passed.",
            ),
        )
    )
    write_regression_manifest(manifest, manifest_path)

    report = build_beta_readiness_report(
        tmp_path / "runs",
        physical_status=_passed_physical_status(),
        trusted_feedback_status=_passed_trusted_feedback_status(),
        environment_report=_ready_environment_report(),
        regression_manifest_path=manifest_path,
    )

    gates = {gate["id"]: gate for gate in report["gates"]}
    regression_gate = gates["beta_regressions"]

    assert report["overall_status"] == "action_required"
    assert regression_gate["status"] == "action_required"
    assert "1 regression case(s) drifted" in regression_gate["detail"]
    assert "printpipe run-regressions" in regression_gate["action"]
    assert report["regression_status"]["failed_count"] == 1


def _passed_physical_status() -> dict[str, object]:
    return {
        "overall_status": "passed",
        "required_families": ["pla", "petg", "tpu"],
        "family_status": {
            "pla": {"status": "passed"},
            "petg": {"status": "passed"},
            "tpu": {"status": "passed"},
        },
    }


def _passed_trusted_feedback_status() -> dict[str, object]:
    return {
        "overall_status": "passed",
        "required_trusted_user_count": 3,
        "unique_trusted_user_count": 3,
        "missing_trusted_user_count": 0,
        "trusted_users": ["Lee", "Maya", "Sam"],
        "packet_count": 3,
        "trusted_user_packet_count": 3,
    }


def _ready_environment_report() -> dict[str, object]:
    return {
        "platform": {"raw": "darwin", "normalized": "macos"},
        "dependencies": [{"id": "python", "status": "ok"}],
        "bambu_studio": {"installed_count": 1},
        "bambu_profiles": {"candidate_count": 1},
        "filesystem": {"checks": [{"status": "ok"}]},
        "system": {"signing": {"status": "ready", "missing_tools": [], "missing_identities": []}},
    }
