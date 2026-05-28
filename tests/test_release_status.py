from __future__ import annotations

import json
from pathlib import Path

from printpipe.cli import build_parser, main
from printpipe.packaging.release_status import (
    build_release_status_report,
    render_release_status_report,
)
from printpipe.packaging.release_plan import (
    build_release_distribution_plan,
    render_release_distribution_plan,
    start_release_distribution_handoff,
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


def test_release_status_report_passes_regression_manifest_to_readiness(
    monkeypatch,
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "regression_manifest.json"
    observed: dict[str, Path | None] = {}

    def fake_readiness_report(runs_dir, *, regression_manifest_path=None):
        observed["runs_dir"] = Path(runs_dir)
        observed["regression_manifest_path"] = regression_manifest_path
        return {
            "overall_status": "action_required",
            "action_required_count": 1,
            "gates": [
                {
                    "id": "beta_regressions",
                    "label": "Beta regressions",
                    "status": "action_required",
                    "detail": "1 regression case(s) drifted from expected outcomes.",
                    "action": "Run printpipe run-regressions manifest --strict.",
                }
            ],
        }

    monkeypatch.setattr(
        "printpipe.packaging.release_status.build_beta_readiness_report",
        fake_readiness_report,
    )

    report = build_release_status_report(
        release_dir=tmp_path / "release",
        runs_dir=tmp_path / "runs",
        release_verification={
            "status": "ok",
            "artifact_count": 1,
            "checks": [],
            "failures": [],
            "artifacts": [],
        },
        regression_manifest_path=manifest_path,
    )

    gates = {gate["id"]: gate for gate in report["gates"]}
    assert observed == {
        "runs_dir": tmp_path / "runs",
        "regression_manifest_path": manifest_path,
    }
    assert report["overall_status"] == "action_required"
    assert gates["beta_regressions"]["status"] == "action_required"
    assert report["next_actions"] == ["Run printpipe run-regressions manifest --strict."]


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


def test_release_distribution_plan_turns_distribution_gates_into_commands(
    tmp_path: Path,
) -> None:
    release_dir = tmp_path / "release"
    runs_dir = tmp_path / "runs"
    plan = build_release_distribution_plan(
        release_dir=release_dir,
        runs_dir=runs_dir,
        release_status_report={
            "overall_status": "action_required",
            "action_required_count": 2,
            "release_dir": str(release_dir),
            "runs_dir": str(runs_dir),
            "gates": [
                {
                    "id": "release_bundle",
                    "label": "Release bundle",
                    "status": "ready",
                    "detail": "Release manifest and 4 artifacts verify.",
                    "action": "No action needed.",
                },
                {
                    "id": "macos_distribution",
                    "label": "macOS distribution",
                    "status": "action_required",
                    "detail": "macOS release artifact is not Developer ID signed and notarized.",
                    "action": "Install Developer ID identities, configure notarytool, and rebuild the release DMG.",
                },
                {
                    "id": "windows_distribution",
                    "label": "Windows distribution",
                    "status": "action_required",
                    "detail": "No signed Windows installer artifact is recorded in the manifest.",
                    "action": "Build and include a signed PrintPipeSetup.exe before a strict release handoff.",
                },
            ],
        },
    )

    actions = {action["id"]: action for action in plan["actions"]}
    assert plan["overall_status"] == "action_required"
    assert plan["action_count"] == 2
    assert "not signed distribution evidence" in plan["proof_boundary"]
    assert actions["macos_distribution"]["status"] == "action_required"
    assert "build-release" in actions["macos_distribution"]["command"]
    assert "--developer-id-identity" in actions["macos_distribution"]["command"]
    assert "--notary-profile" in actions["macos_distribution"]["command"]
    assert actions["windows_distribution"]["status"] == "action_required"
    assert "build-windows-installer" in actions["windows_distribution"]["command"]
    assert "build-release" in actions["windows_distribution"]["followup_command"]
    assert "--windows-installer-exe" in actions["windows_distribution"]["followup_command"]


def test_release_distribution_start_writes_handoff_without_signed_evidence(
    tmp_path: Path,
) -> None:
    release_dir = tmp_path / "dist" / "release"
    runs_dir = tmp_path / "runs"
    status_report = {
        "overall_status": "action_required",
        "action_required_count": 2,
        "release_dir": str(release_dir),
        "runs_dir": str(runs_dir),
        "gates": [
            {
                "id": "macos_distribution",
                "label": "macOS distribution",
                "status": "action_required",
                "detail": "macOS release artifact is not Developer ID signed and notarized.",
                "action": "Install Developer ID identities, configure notarytool, and rebuild the release DMG.",
            },
            {
                "id": "windows_distribution",
                "label": "Windows distribution",
                "status": "action_required",
                "detail": "No signed Windows installer artifact is recorded in the manifest.",
                "action": "Build and include a signed PrintPipeSetup.exe before a strict release handoff.",
            },
        ],
    }

    result = start_release_distribution_handoff(
        release_dir=release_dir,
        runs_dir=runs_dir,
        regression_manifest_path=tmp_path / "regressions.json",
        release_status_report=status_report,
    )
    plan = build_release_distribution_plan(
        release_dir=release_dir,
        runs_dir=runs_dir,
        regression_manifest_path=tmp_path / "regressions.json",
        release_status_report=status_report,
    )
    rendered = render_release_distribution_plan(plan)

    handoff_path = tmp_path / "dist" / "release_handoffs" / "release_distribution_handoff.md"
    handoff = handoff_path.read_text(encoding="utf-8")
    actions = {action["id"]: action for action in plan["actions"]}

    assert result["status"] == "started"
    assert result["handoff_markdown_path"] == str(handoff_path.resolve())
    assert not (release_dir / "release_manifest.json").exists()
    assert "PrintPipe Release Distribution Handoff" in handoff
    assert "Developer ID Application certificate" in handoff
    assert "Code-signing certificate" in handoff
    assert "Only verified release manifest artifacts" in handoff
    assert "printpipe release-status" in handoff
    assert actions["macos_distribution"]["start_command"].startswith("printpipe release-start")
    assert actions["macos_distribution"]["handoff_markdown_path"] == str(handoff_path.resolve())
    assert actions["windows_distribution"]["handoff_markdown_path"] == str(handoff_path.resolve())
    assert "start: printpipe release-start" in rendered
    assert f"handoff: {handoff_path.resolve()}" in rendered


def test_release_distribution_plan_ready_when_release_status_ready(
    tmp_path: Path,
) -> None:
    plan = build_release_distribution_plan(
        release_dir=tmp_path / "release",
        runs_dir=tmp_path / "runs",
        release_status_report={
            "overall_status": "ready",
            "action_required_count": 0,
            "release_dir": str(tmp_path / "release"),
            "runs_dir": str(tmp_path / "runs"),
            "gates": [
                {
                    "id": "release_bundle",
                    "label": "Release bundle",
                    "status": "ready",
                    "detail": "Release manifest and artifacts verify.",
                    "action": "No action needed.",
                },
                {
                    "id": "macos_distribution",
                    "label": "macOS distribution",
                    "status": "ready",
                    "detail": "A Developer ID signed and notarized macOS DMG is recorded.",
                    "action": "No action needed.",
                },
                {
                    "id": "windows_distribution",
                    "label": "Windows distribution",
                    "status": "ready",
                    "detail": "A signed Windows installer artifact is recorded.",
                    "action": "No action needed.",
                },
            ],
        },
    )

    assert plan["overall_status"] == "ready"
    assert plan["action_count"] == 0
    assert plan["actions"] == []


def test_render_release_distribution_plan_lists_commands(tmp_path: Path) -> None:
    plan = build_release_distribution_plan(
        release_dir=tmp_path / "release",
        runs_dir=tmp_path / "runs",
        release_status_report={
            "overall_status": "action_required",
            "action_required_count": 1,
            "release_dir": str(tmp_path / "release"),
            "runs_dir": str(tmp_path / "runs"),
            "gates": [
                {
                    "id": "macos_distribution",
                    "label": "macOS distribution",
                    "status": "action_required",
                    "detail": "macOS release artifact is not Developer ID signed and notarized.",
                    "action": "Install Developer ID identities, configure notarytool, and rebuild the release DMG.",
                }
            ],
        },
    )

    rendered = render_release_distribution_plan(plan)

    assert "PrintPipe Release Distribution Plan" in rendered
    assert "overall: action_required" in rendered
    assert "macos_distribution" in rendered
    assert "build-release" in rendered
    assert "not signed distribution evidence" in rendered


def test_release_plan_parser_accepts_dirs_json_and_regression_manifest(
    tmp_path: Path,
) -> None:
    args = build_parser().parse_args(
        [
            "release-plan",
            "--release-dir",
            str(tmp_path / "release"),
            "--runs-dir",
            str(tmp_path / "runs"),
            "--regression-manifest",
            str(tmp_path / "regression_manifest.json"),
            "--json",
        ]
    )

    assert args.command == "release-plan"
    assert args.release_dir == tmp_path / "release"
    assert args.runs_dir == tmp_path / "runs"
    assert args.regression_manifest == tmp_path / "regression_manifest.json"
    assert args.json is True


def test_release_start_parser_accepts_dirs_json_and_regression_manifest(
    tmp_path: Path,
) -> None:
    args = build_parser().parse_args(
        [
            "release-start",
            "--release-dir",
            str(tmp_path / "release"),
            "--runs-dir",
            str(tmp_path / "runs"),
            "--regression-manifest",
            str(tmp_path / "regression_manifest.json"),
            "--json",
        ]
    )

    assert args.command == "release-start"
    assert args.release_dir == tmp_path / "release"
    assert args.runs_dir == tmp_path / "runs"
    assert args.regression_manifest == tmp_path / "regression_manifest.json"
    assert args.json is True


def test_cli_release_plan_prints_json(monkeypatch, tmp_path: Path, capsys) -> None:
    manifest_path = tmp_path / "regression_manifest.json"

    def fake_release_plan(*, release_dir, runs_dir, regression_manifest_path=None):
        assert release_dir == tmp_path / "release"
        assert runs_dir == tmp_path / "runs"
        assert regression_manifest_path == manifest_path
        return {
            "schema_version": 1,
            "overall_status": "action_required",
            "action_count": 1,
            "proof_boundary": "plan only",
            "actions": [{"id": "macos_distribution", "status": "action_required"}],
        }

    monkeypatch.setattr(
        "printpipe.packaging.release_plan.build_release_distribution_plan",
        fake_release_plan,
    )

    exit_code = main(
        [
            "release-plan",
            "--release-dir",
            str(tmp_path / "release"),
            "--runs-dir",
            str(tmp_path / "runs"),
            "--regression-manifest",
            str(manifest_path),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["overall_status"] == "action_required"
    assert payload["actions"][0]["id"] == "macos_distribution"


def test_cli_release_start_prints_handoff_json(tmp_path: Path, capsys) -> None:
    exit_code = main(
        [
            "release-start",
            "--release-dir",
            str(tmp_path / "release"),
            "--runs-dir",
            str(tmp_path / "runs"),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "started"
    assert payload["handoff_markdown_path"].endswith(
        "release_handoffs/release_distribution_handoff.md"
    )
    assert "release-status" in payload["release_status_command"]
    assert "final-plan" in payload["final_plan_command"]


def test_release_status_parser_accepts_dirs_json_and_strict_flags(tmp_path: Path) -> None:
    args = build_parser().parse_args(
        [
            "release-status",
            "--release-dir",
            str(tmp_path / "release"),
            "--runs-dir",
            str(tmp_path / "runs"),
            "--regression-manifest",
            str(tmp_path / "regression_manifest.json"),
            "--json",
            "--strict",
        ]
    )

    assert args.command == "release-status"
    assert args.release_dir == tmp_path / "release"
    assert args.runs_dir == tmp_path / "runs"
    assert args.regression_manifest == tmp_path / "regression_manifest.json"
    assert args.json is True
    assert args.strict is True


def test_cli_release_status_json_returns_two_when_strict_and_action_required(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    manifest_path = tmp_path / "regression_manifest.json"

    def fake_release_status_report(*, release_dir, runs_dir, regression_manifest_path=None):
        assert regression_manifest_path == manifest_path
        return {
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
        }

    monkeypatch.setattr(
        "printpipe.packaging.release_status.build_release_status_report",
        fake_release_status_report,
    )

    exit_code = main(
        [
            "release-status",
            "--release-dir",
            str(tmp_path / "release"),
            "--runs-dir",
            str(tmp_path / "runs"),
            "--regression-manifest",
            str(manifest_path),
            "--json",
            "--strict",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert payload["overall_status"] == "action_required"
    assert payload["next_actions"] == ["Build and verify a release bundle."]
