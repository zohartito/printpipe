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
        media_meshgen_smoke_status=_passed_media_smoke_status(),
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
        media_meshgen_smoke_status=_passed_media_smoke_status(),
    )

    gates = {gate["id"]: gate for gate in report["gates"]}
    regression_gate = gates["beta_regressions"]

    assert report["overall_status"] == "ready"
    assert regression_gate["status"] == "not_applicable"
    assert "No beta regression manifest configured" in regression_gate["detail"]
    assert report["regression_status"]["overall_status"] == "not_configured"


def test_beta_readiness_report_blocks_on_incomplete_rule_update_packets(
    tmp_path: Path,
) -> None:
    report = build_beta_readiness_report(
        tmp_path / "runs",
        physical_status=_passed_physical_status(),
        trusted_feedback_status=_passed_trusted_feedback_status(),
        environment_report=_ready_environment_report(),
        media_meshgen_smoke_status=_passed_media_smoke_status(),
        rule_update_status={
            "overall_status": "incomplete",
            "missing_rule_types": ["material", "repair"],
            "verified_rule_types": ["orientation"],
        },
    )

    gates = {gate["id"]: gate for gate in report["gates"]}
    rule_gate = gates["rule_updates"]

    assert report["overall_status"] == "action_required"
    assert rule_gate["status"] == "action_required"
    assert "material, repair" in rule_gate["detail"]
    assert "record-rule-update" in rule_gate["action"]


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
    assert "0 / 3 trusted users completed feedback" in trusted_gate["detail"]
    assert "recorded feedback" not in trusted_gate["detail"]
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


def test_beta_readiness_report_blocks_when_captured_failures_lack_regressions(
    tmp_path: Path,
) -> None:
    report = build_beta_readiness_report(
        tmp_path / "runs",
        physical_status=_passed_physical_status(),
        trusted_feedback_status=_passed_trusted_feedback_status(),
        rule_update_status=_passed_rule_update_status(),
        environment_report=_ready_environment_report(),
        failure_regression_status={
            "overall_status": "missing_regressions",
            "failure_report_count": 2,
            "covered_failure_count": 1,
            "missing_regression_source_run_ids": ["run-missing"],
        },
    )

    gates = {gate["id"]: gate for gate in report["gates"]}
    gate = gates["failure_regressions"]

    assert report["overall_status"] == "action_required"
    assert gate["status"] == "action_required"
    assert "1 / 2 captured failures" in gate["detail"]
    assert "run-missing" in gate["detail"]


def test_beta_readiness_report_blocks_rule_updates_when_failures_have_no_packets(
    tmp_path: Path,
) -> None:
    report = build_beta_readiness_report(
        tmp_path / "runs",
        physical_status=_passed_physical_status(),
        trusted_feedback_status=_passed_trusted_feedback_status(),
        rule_update_status={
            "overall_status": "missing",
            "verified_rule_types": [],
            "missing_rule_types": ["material", "orientation", "repair"],
        },
        environment_report=_ready_environment_report(),
        failure_regression_status={
            "overall_status": "missing_regressions",
            "failure_report_count": 1,
            "covered_failure_count": 0,
            "missing_regression_source_run_ids": ["failed-run"],
        },
    )

    gates = {gate["id"]: gate for gate in report["gates"]}
    gate = gates["rule_updates"]

    assert report["overall_status"] == "action_required"
    assert gate["status"] == "action_required"
    assert "1 captured failure" in gate["detail"]
    assert "record-rule-update" in gate["action"]


def test_beta_readiness_report_blocks_when_media_meshgen_provider_unavailable(
    tmp_path: Path,
) -> None:
    environment = _ready_environment_report()
    environment["meshgen"] = {
        "overall_status": "action_required",
        "live_media_provider_count": 0,
        "message": "No live image/GIF/video meshgen provider is configured.",
        "action": (
            "Run printpipe media-meshgen-template --preset comfyui-api "
            "--output scripts/media_meshgen_adapter.py, "
            "set PRINTPIPE_MEDIA_MESHGEN_COMMAND, set PRINTPIPE_HUNYUAN3D_COMMAND, "
            "or configure a hosted mesh provider."
        ),
        "providers": [
            {
                "provider_id": "hunyuan3d",
                "status": "skipped",
                "message": "Hunyuan3D local command is not configured.",
            }
        ],
    }

    report = build_beta_readiness_report(
        tmp_path / "runs",
        physical_status=_passed_physical_status(),
        trusted_feedback_status=_passed_trusted_feedback_status(),
        rule_update_status=_passed_rule_update_status(),
        environment_report=environment,
        media_meshgen_smoke_status=_passed_media_smoke_status(),
    )

    gates = {gate["id"]: gate for gate in report["gates"]}
    gate = gates["media_meshgen"]
    assert report["overall_status"] == "action_required"
    assert gate["status"] == "action_required"
    assert "No live image/GIF/video meshgen provider" in gate["detail"]
    assert "printpipe media-meshgen-template" in gate["action"]
    assert "PRINTPIPE_MEDIA_MESHGEN_COMMAND" in gate["action"]
    assert "PRINTPIPE_HUNYUAN3D_COMMAND" in gate["action"]


def test_beta_readiness_report_blocks_when_media_provider_lacks_smoke_evidence(
    tmp_path: Path,
) -> None:
    report = build_beta_readiness_report(
        tmp_path / "runs",
        physical_status=_passed_physical_status(),
        trusted_feedback_status=_passed_trusted_feedback_status(),
        rule_update_status=_passed_rule_update_status(),
        environment_report=_ready_environment_report(),
        media_meshgen_smoke_status={
            "overall_status": "missing",
            "successful_smoke_count": 0,
            "action": "Run printpipe media-meshgen-smoke reference.png --runs-dir runs/media-meshgen-smoke.",
        },
    )

    gate = {gate["id"]: gate for gate in report["gates"]}["media_meshgen"]
    assert report["overall_status"] == "action_required"
    assert gate["status"] == "action_required"
    assert "configured, but no successful smoke receipt" in gate["detail"]
    assert "media-meshgen-smoke" in gate["action"]


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


def _passed_rule_update_status() -> dict[str, object]:
    return {
        "overall_status": "passed",
        "verified_rule_types": ["material", "orientation", "repair"],
        "missing_rule_types": [],
        "packet_count": 3,
    }


def _passed_media_smoke_status() -> dict[str, object]:
    return {
        "overall_status": "passed",
        "successful_smoke_count": 1,
        "latest_successful_smoke": {
            "run_id": "media-smoke-ok",
            "provider_id": "media_command",
            "output_path": "20_meshgen/media_command.stl",
        },
    }


def _ready_environment_report() -> dict[str, object]:
    return {
        "platform": {"raw": "darwin", "normalized": "macos"},
        "dependencies": [{"id": "python", "status": "ok"}],
        "bambu_studio": {"installed_count": 1},
        "bambu_profiles": {"candidate_count": 1},
        "filesystem": {"checks": [{"status": "ok"}]},
        "meshgen": {
            "overall_status": "ready",
            "live_media_provider_count": 1,
            "message": "At least one live media meshgen provider is configured.",
            "action": "No action needed.",
        },
        "system": {"signing": {"status": "ready", "missing_tools": [], "missing_identities": []}},
    }
