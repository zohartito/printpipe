from __future__ import annotations

import json
from pathlib import Path

from printpipe.cli import build_parser, main
from printpipe.packaging.release_status import (
    build_release_status_report,
    render_release_status_report,
)


def test_release_status_report_combines_release_and_readiness_gates(tmp_path: Path) -> None:
    report = build_release_status_report(
        release_dir=tmp_path / "release",
        runs_dir=tmp_path / "runs",
        release_verification={
            "status": "ok",
            "artifact_count": 4,
            "checks": [{"id": "manifest_exists", "status": "ok"}],
            "failures": [],
        },
        readiness_report={
            "overall_status": "action_required",
            "action_required_count": 1,
            "gates": [
                {
                    "id": "physical_validation",
                    "label": "Physical validation",
                    "status": "action_required",
                    "detail": "Missing passed TPU evidence.",
                    "action": "Print and record TPU evidence.",
                }
            ],
        },
    )

    gates = {gate["id"]: gate for gate in report["gates"]}
    assert report["overall_status"] == "action_required"
    assert report["action_required_count"] == 1
    assert gates["release_bundle"]["status"] == "ready"
    assert gates["physical_validation"]["status"] == "action_required"
    assert report["next_actions"] == ["Print and record TPU evidence."]


def test_release_status_report_blocks_on_failed_release_verification(tmp_path: Path) -> None:
    report = build_release_status_report(
        release_dir=tmp_path / "release",
        runs_dir=tmp_path / "runs",
        release_verification={
            "status": "failed",
            "artifact_count": 3,
            "checks": [],
            "failures": [
                {"id": "artifact_exists:macos_dmg", "message": "artifact exists"},
                {"id": "artifact_sha256:zipapp", "message": "artifact sha256 matches manifest"},
            ],
        },
        readiness_report={
            "overall_status": "ready",
            "action_required_count": 0,
            "gates": [],
        },
    )

    gates = {gate["id"]: gate for gate in report["gates"]}
    assert report["overall_status"] == "action_required"
    assert report["action_required_count"] == 1
    assert gates["release_bundle"]["status"] == "action_required"
    assert "2 release verification check(s) failed" in gates["release_bundle"]["detail"]
    assert "Run printpipe verify-release" in gates["release_bundle"]["action"]


def test_release_status_report_blocks_on_unsigned_distribution_artifacts(
    tmp_path: Path,
) -> None:
    report = build_release_status_report(
        release_dir=tmp_path / "release",
        runs_dir=tmp_path / "runs",
        release_verification={
            "status": "ok",
            "artifact_count": 3,
            "checks": [],
            "failures": [],
            "artifacts": [
                {"kind": "macos_dmg", "signed": True, "notarized": False},
                {"kind": "windows_portable", "signed": False},
            ],
        },
        readiness_report={
            "overall_status": "ready",
            "action_required_count": 0,
            "gates": [],
        },
    )

    gates = {gate["id"]: gate for gate in report["gates"]}
    assert report["overall_status"] == "action_required"
    assert gates["macos_distribution"]["status"] == "action_required"
    assert "not Developer ID signed and notarized" in gates["macos_distribution"]["detail"]
    assert gates["windows_distribution"]["status"] == "action_required"
    assert "No signed Windows installer artifact" in gates["windows_distribution"]["detail"]


def test_release_status_report_accepts_final_distribution_artifacts(tmp_path: Path) -> None:
    report = build_release_status_report(
        release_dir=tmp_path / "release",
        runs_dir=tmp_path / "runs",
        release_verification={
            "status": "ok",
            "artifact_count": 5,
            "checks": [],
            "failures": [],
            "artifacts": [
                {
                    "kind": "macos_dmg",
                    "signed": True,
                    "notarized": True,
                    "signing_kind": "developer_id_application",
                },
                {"kind": "windows_installer", "signed": True},
            ],
        },
        readiness_report={
            "overall_status": "ready",
            "action_required_count": 0,
            "gates": [],
        },
    )

    gates = {gate["id"]: gate for gate in report["gates"]}
    assert report["overall_status"] == "ready"
    assert gates["macos_distribution"]["status"] == "ready"
    assert gates["windows_distribution"]["status"] == "ready"


def test_render_release_status_report_lists_next_actions(tmp_path: Path) -> None:
    rendered = render_release_status_report(
        {
            "overall_status": "action_required",
            "action_required_count": 2,
            "release_dir": str(tmp_path / "release"),
            "runs_dir": str(tmp_path / "runs"),
            "gates": [
                {
                    "id": "release_bundle",
                    "label": "Release bundle",
                    "status": "ready",
                    "detail": "Release manifest and artifacts verify.",
                    "action": "No action needed.",
                }
            ],
            "next_actions": ["Record TPU evidence.", "Install Developer ID certificate."],
        }
    )

    assert "PrintPipe Release Status" in rendered
    assert "overall: action_required" in rendered
    assert "- ready: Release bundle - Release manifest and artifacts verify." in rendered
    assert "Next actions:" in rendered
    assert "- Record TPU evidence." in rendered
    assert "- Install Developer ID certificate." in rendered


def test_release_status_parser_accepts_dirs_json_and_strict_flags(tmp_path: Path) -> None:
    args = build_parser().parse_args(
        [
            "release-status",
            "--release-dir",
            str(tmp_path / "release"),
            "--runs-dir",
            str(tmp_path / "runs"),
            "--json",
            "--strict",
        ]
    )

    assert args.command == "release-status"
    assert args.release_dir == tmp_path / "release"
    assert args.runs_dir == tmp_path / "runs"
    assert args.json is True
    assert args.strict is True


def test_cli_release_status_json_returns_two_when_strict_and_action_required(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    monkeypatch.setattr(
        "printpipe.packaging.release_status.build_release_status_report",
        lambda *, release_dir, runs_dir: {
            "schema_version": 1,
            "overall_status": "action_required",
            "action_required_count": 1,
            "release_dir": str(release_dir),
            "runs_dir": str(runs_dir),
            "gates": [
                {
                    "id": "release_bundle",
                    "label": "Release bundle",
                    "status": "action_required",
                    "detail": "release_manifest.json is missing.",
                    "action": "Build and verify a release bundle.",
                }
            ],
            "next_actions": ["Build and verify a release bundle."],
        },
    )

    exit_code = main(
        [
            "release-status",
            "--release-dir",
            str(tmp_path / "release"),
            "--runs-dir",
            str(tmp_path / "runs"),
            "--json",
            "--strict",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert payload["overall_status"] == "action_required"
    assert payload["next_actions"] == ["Build and verify a release bundle."]
