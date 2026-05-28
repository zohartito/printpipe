from __future__ import annotations

from pathlib import Path

from printpipe.beta.readiness import build_beta_readiness_report


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
    assert gates["signing"]["status"] == "action_required"
    assert "PLA, PETG, and TPU" in gates["physical_validation"]["action"]
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
        environment_report=environment_report,
    )

    assert report["overall_status"] == "ready"
    assert all(gate["status"] == "ready" for gate in report["gates"])
