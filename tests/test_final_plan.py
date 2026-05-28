from __future__ import annotations

import json
from pathlib import Path

from printpipe.cli import build_parser, main
from printpipe.final_plan import (
    build_final_action_plan,
    build_final_next_action_payload,
    render_final_action_plan,
    render_final_next_action,
)


def test_final_action_plan_orders_remaining_external_gates(tmp_path: Path) -> None:
    plan = build_final_action_plan(
        runs_dir=tmp_path / "runs",
        release_dir=tmp_path / "release",
        physical_plan={
            "overall_status": "action_required",
            "action_count": 3,
            "proof_boundary": "physical proof only",
            "actions": [{"family": "pla"}, {"family": "petg"}, {"family": "tpu"}],
        },
        trusted_feedback_plan={
            "overall_status": "action_required",
            "action_count": 2,
            "proof_boundary": "feedback proof only",
            "actions": [{"slot": 2}, {"slot": 3}],
        },
        release_plan={
            "overall_status": "action_required",
            "action_count": 3,
            "proof_boundary": "release proof only",
            "actions": [{"id": "macos_distribution"}, {"id": "windows_distribution"}, {"id": "signing"}],
        },
    )

    assert plan["overall_status"] == "action_required"
    assert plan["action_count"] == 8
    assert plan["next_action"]["section_id"] == "physical_validation"
    assert plan["next_action"]["action_id"] == "pla"
    assert plan["next_action"]["label"] == "PLA"
    assert plan["next_action"]["command"].startswith(
        "printpipe physical-plan --runs-dir "
    )
    assert plan["next_command"] == plan["next_action"]["command"]
    assert [section["id"] for section in plan["sections"]] == [
        "physical_validation",
        "trusted_user_beta",
        "release_distribution",
    ]
    assert [section["action_count"] for section in plan["sections"]] == [3, 2, 3]
    assert plan["sections"][0]["command"].startswith("printpipe physical-plan")
    assert plan["sections"][1]["command"].startswith("printpipe beta-feedback-plan")
    assert plan["sections"][2]["command"].startswith("printpipe release-plan")
    assert "not evidence" in plan["proof_boundary"]


def test_final_action_plan_reports_ready_when_all_sections_ready(tmp_path: Path) -> None:
    plan = build_final_action_plan(
        runs_dir=tmp_path / "runs",
        release_dir=tmp_path / "release",
        physical_plan={"overall_status": "passed", "action_count": 0, "actions": []},
        trusted_feedback_plan={"overall_status": "ready", "action_count": 0, "actions": []},
        release_plan={"overall_status": "ready", "action_count": 0, "actions": []},
    )

    assert plan["overall_status"] == "ready"
    assert plan["action_count"] == 0
    assert plan["next_action"] == {}
    assert plan["next_command"] == ""


def test_final_action_plan_prefers_action_specific_start_command(
    tmp_path: Path,
) -> None:
    plan = build_final_action_plan(
        runs_dir=tmp_path / "runs",
        release_dir=tmp_path / "release",
        physical_plan={
            "overall_status": "action_required",
            "action_count": 1,
            "proof_boundary": "physical proof only",
            "actions": [
                {
                    "family": "tpu",
                    "status": "missing",
                    "reason": "no packet",
                    "start_command": "printpipe physical-start --family tpu",
                    "record_command": "printpipe record-physical-evidence runs/tpu",
                }
            ],
        },
        trusted_feedback_plan={"overall_status": "ready", "action_count": 0, "actions": []},
        release_plan={"overall_status": "ready", "action_count": 0, "actions": []},
    )

    assert plan["next_action"] == {
        "section_id": "physical_validation",
        "section_label": "Physical validation",
        "action_id": "tpu",
        "label": "TPU",
        "status": "missing",
        "detail": "no packet",
        "command": "printpipe physical-start --family tpu",
        "command_kind": "start_command",
    }
    assert plan["next_command"] == "printpipe physical-start --family tpu"


def test_final_action_plan_next_action_keeps_handoff_and_artifact_paths(
    tmp_path: Path,
) -> None:
    plan = build_final_action_plan(
        runs_dir=tmp_path / "runs",
        release_dir=tmp_path / "release",
        physical_plan={
            "overall_status": "action_required",
            "action_count": 1,
            "proof_boundary": "physical proof only",
            "actions": [
                {
                    "family": "pla",
                    "status": "recorded_but_not_passed",
                    "reason": "no passed physical evidence",
                    "record_command": "printpipe record-physical-evidence runs/pla",
                    "coupon_stl_path": "runs/pla/40_geometry/coupon.stl",
                    "coupon_json_path": "runs/pla/40_geometry/coupon.json",
                    "handoff_markdown_path": "runs/pla/90_physical/handoff.md",
                }
            ],
        },
        trusted_feedback_plan={"overall_status": "ready", "action_count": 0, "actions": []},
        release_plan={"overall_status": "ready", "action_count": 0, "actions": []},
    )

    assert plan["next_action"]["command"] == "printpipe record-physical-evidence runs/pla"
    assert plan["next_action"]["coupon_stl_path"] == "runs/pla/40_geometry/coupon.stl"
    assert plan["next_action"]["coupon_json_path"] == "runs/pla/40_geometry/coupon.json"
    assert plan["next_action"]["handoff_markdown_path"] == "runs/pla/90_physical/handoff.md"


def test_final_action_plan_prefers_print_handoff_command_before_record_command(
    tmp_path: Path,
) -> None:
    plan = build_final_action_plan(
        runs_dir=tmp_path / "runs",
        release_dir=tmp_path / "release",
        physical_plan={
            "overall_status": "action_required",
            "action_count": 1,
            "proof_boundary": "physical proof only",
            "actions": [
                {
                    "family": "pla",
                    "status": "recorded_but_not_passed",
                    "detail": "print first, then record",
                    "command": "printpipe open-folder runs/pla --target run",
                    "command_kind": "print_handoff_command",
                    "record_command": "printpipe record-physical-evidence runs/pla",
                    "coupon_stl_path": "runs/pla/40_geometry/coupon.stl",
                }
            ],
        },
        trusted_feedback_plan={"overall_status": "ready", "action_count": 0, "actions": []},
        release_plan={"overall_status": "ready", "action_count": 0, "actions": []},
    )

    assert plan["next_action"]["command"] == "printpipe open-folder runs/pla --target run"
    assert plan["next_action"]["command_kind"] == "print_handoff_command"
    assert plan["next_action"]["detail"] == "print first, then record"
    assert (
        plan["next_action"]["record_command"]
        == "printpipe record-physical-evidence runs/pla"
    )
    assert plan["next_action"]["coupon_stl_path"] == "runs/pla/40_geometry/coupon.stl"


def test_final_action_plan_release_next_action_keeps_commands_and_required_inputs(
    tmp_path: Path,
) -> None:
    plan = build_final_action_plan(
        runs_dir=tmp_path / "runs",
        release_dir=tmp_path / "release",
        physical_plan={"overall_status": "passed", "action_count": 0, "actions": []},
        trusted_feedback_plan={"overall_status": "ready", "action_count": 0, "actions": []},
        release_plan={
            "overall_status": "action_required",
            "action_count": 1,
            "proof_boundary": "release proof only",
            "actions": [
                {
                    "id": "macos_distribution",
                    "label": "macOS distribution",
                    "status": "action_required",
                    "detail": "sign and notarize",
                    "start_command": "printpipe release-start --release-dir dist/release",
                    "command": "printpipe build-release --developer-id-identity '<id>'",
                    "followup_command": "printpipe release-status --strict",
                    "handoff_markdown_path": "dist/release_handoffs/release_distribution_handoff.md",
                    "required_inputs": [
                        "Developer ID Application certificate",
                        "notarytool keychain profile",
                    ],
                }
            ],
        },
    )

    next_action = plan["next_action"]
    assert next_action["section_id"] == "release_distribution"
    assert next_action["command"] == "printpipe release-start --release-dir dist/release"
    assert next_action["command_kind"] == "start_command"
    assert next_action["run_command"] == (
        "printpipe build-release --developer-id-identity '<id>'"
    )
    assert next_action["followup_command"] == "printpipe release-status --strict"
    assert next_action["required_inputs"] == [
        "Developer ID Application certificate",
        "notarytool keychain profile",
    ]
    assert next_action["handoff_markdown_path"].endswith(
        "release_distribution_handoff.md"
    )


def test_render_final_action_plan_keeps_proof_boundaries(tmp_path: Path) -> None:
    plan = build_final_action_plan(
        runs_dir=tmp_path / "runs",
        release_dir=tmp_path / "release",
        physical_plan={
            "overall_status": "action_required",
            "action_count": 1,
            "proof_boundary": "physical proof only",
            "actions": [{"family": "tpu"}],
        },
        trusted_feedback_plan={
            "overall_status": "ready",
            "action_count": 0,
            "proof_boundary": "feedback proof only",
            "actions": [],
        },
        release_plan={
            "overall_status": "action_required",
            "action_count": 1,
            "proof_boundary": "release proof only",
            "actions": [{"id": "signing"}],
        },
    )

    rendered = render_final_action_plan(plan)

    assert "PrintPipe Final Action Plan" in rendered
    assert "overall: action_required" in rendered
    assert "physical_validation" in rendered
    assert "trusted_user_beta" in rendered
    assert "release_distribution" in rendered
    assert "Next action:" in rendered
    assert "command: printpipe physical-plan" in rendered
    assert "physical proof only" in rendered
    assert "release proof only" in rendered
    assert "printpipe release-plan" in rendered


def test_render_final_action_plan_lists_next_action_supporting_paths(
    tmp_path: Path,
) -> None:
    plan = {
        "overall_status": "action_required",
        "action_count": 1,
        "runs_dir": str(tmp_path / "runs"),
        "release_dir": str(tmp_path / "release"),
        "proof_boundary": "A final plan is not evidence.",
        "next_action": {
            "section_label": "Physical validation",
            "label": "PLA",
            "status": "recorded_but_not_passed",
            "detail": "no passed physical evidence",
            "command": "printpipe record-physical-evidence runs/pla",
            "coupon_stl_path": "runs/pla/40_geometry/coupon.stl",
            "coupon_json_path": "runs/pla/40_geometry/coupon.json",
            "handoff_markdown_path": "runs/pla/90_physical/handoff.md",
        },
        "sections": [],
    }

    rendered = render_final_action_plan(plan)

    assert "artifact: runs/pla/40_geometry/coupon.stl" in rendered
    assert "sidecar: runs/pla/40_geometry/coupon.json" in rendered
    assert "handoff: runs/pla/90_physical/handoff.md" in rendered


def test_render_final_next_action_shows_only_immediate_action() -> None:
    plan = {
        "overall_status": "action_required",
        "action_count": 9,
        "proof_boundary": "A final plan is not evidence.",
        "next_action": {
            "section_label": "Physical validation",
            "label": "PLA",
            "status": "recorded_but_not_passed",
            "detail": "no passed physical evidence",
            "command": "printpipe open-folder runs/pla --target run",
            "record_command": "printpipe record-physical-evidence runs/pla",
            "coupon_stl_path": "runs/pla/40_geometry/coupon.stl",
            "coupon_json_path": "runs/pla/40_geometry/coupon.json",
            "handoff_markdown_path": "runs/pla/90_physical/handoff.md",
        },
        "sections": [
            {"id": "physical_validation", "action_count": 3},
            {"id": "trusted_user_beta", "action_count": 3},
        ],
    }

    rendered = render_final_next_action(plan)

    assert "PrintPipe Final Next Action" in rendered
    assert "Physical validation: PLA (recorded_but_not_passed)" in rendered
    assert "command: printpipe open-folder runs/pla --target run" in rendered
    assert "record after print: printpipe record-physical-evidence runs/pla" in rendered
    assert "artifact: runs/pla/40_geometry/coupon.stl" in rendered
    assert "sidecar: runs/pla/40_geometry/coupon.json" in rendered
    assert "handoff: runs/pla/90_physical/handoff.md" in rendered
    assert "trusted_user_beta" not in rendered


def test_render_final_next_action_shows_release_supporting_commands() -> None:
    rendered = render_final_next_action(
        {
            "overall_status": "action_required",
            "action_count": 1,
            "proof_boundary": "A final plan is not evidence.",
            "next_action": {
                "section_id": "release_distribution",
                "section_label": "Release distribution",
                "label": "macOS distribution",
                "status": "action_required",
                "detail": "sign and notarize",
                "command": "printpipe release-start --release-dir dist/release",
                "run_command": "printpipe build-release --developer-id-identity '<id>'",
                "followup_command": "printpipe release-status --strict",
                "required_inputs": [
                    "Developer ID Application certificate",
                    "notarytool keychain profile",
                ],
                "handoff_markdown_path": "dist/release_handoffs/release_distribution_handoff.md",
            },
        }
    )

    assert "required inputs: Developer ID Application certificate, notarytool keychain profile" in rendered
    assert "run after prerequisites: printpipe build-release --developer-id-identity '<id>'" in rendered
    assert "follow-up check: printpipe release-status --strict" in rendered
    assert "handoff: dist/release_handoffs/release_distribution_handoff.md" in rendered


def test_build_final_next_action_payload_keeps_only_next_action() -> None:
    payload = build_final_next_action_payload(
        {
            "schema_version": 1,
            "overall_status": "action_required",
            "action_count": 2,
            "proof_boundary": "A final plan is not evidence.",
            "next_action": {
                "action_id": "pla",
                "command": "printpipe record-physical-evidence runs/pla",
            },
            "sections": [{"id": "physical_validation"}],
        }
    )

    assert payload == {
        "schema_version": 1,
        "overall_status": "action_required",
        "action_count": 2,
        "proof_boundary": "A final plan is not evidence.",
        "next_action": {
            "action_id": "pla",
            "command": "printpipe record-physical-evidence runs/pla",
        },
        "next_command": "printpipe record-physical-evidence runs/pla",
    }


def test_final_plan_parser_accepts_dirs_json_and_regression_manifest(
    tmp_path: Path,
) -> None:
    args = build_parser().parse_args(
        [
            "final-plan",
            "--release-dir",
            str(tmp_path / "release"),
            "--runs-dir",
            str(tmp_path / "runs"),
            "--regression-manifest",
            str(tmp_path / "regression_manifest.json"),
            "--json",
        ]
    )

    assert args.command == "final-plan"
    assert args.release_dir == tmp_path / "release"
    assert args.runs_dir == tmp_path / "runs"
    assert args.regression_manifest == tmp_path / "regression_manifest.json"
    assert args.json is True


def test_final_next_parser_accepts_dirs_json_and_regression_manifest(
    tmp_path: Path,
) -> None:
    args = build_parser().parse_args(
        [
            "final-next",
            "--release-dir",
            str(tmp_path / "release"),
            "--runs-dir",
            str(tmp_path / "runs"),
            "--regression-manifest",
            str(tmp_path / "regression_manifest.json"),
            "--json",
        ]
    )

    assert args.command == "final-next"
    assert args.release_dir == tmp_path / "release"
    assert args.runs_dir == tmp_path / "runs"
    assert args.regression_manifest == tmp_path / "regression_manifest.json"
    assert args.json is True


def test_cli_final_plan_prints_json(monkeypatch, tmp_path: Path, capsys) -> None:
    manifest_path = tmp_path / "regression_manifest.json"

    def fake_final_plan(*, release_dir, runs_dir, regression_manifest_path=None):
        assert release_dir == tmp_path / "release"
        assert runs_dir == tmp_path / "runs"
        assert regression_manifest_path == manifest_path
        return {
            "schema_version": 1,
            "overall_status": "action_required",
            "action_count": 1,
            "sections": [{"id": "physical_validation", "action_count": 1}],
        }

    monkeypatch.setattr(
        "printpipe.final_plan.build_final_action_plan",
        fake_final_plan,
    )

    exit_code = main(
        [
            "final-plan",
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
    assert payload["sections"][0]["id"] == "physical_validation"


def test_cli_final_next_prints_next_action_json(monkeypatch, tmp_path: Path, capsys) -> None:
    manifest_path = tmp_path / "regression_manifest.json"

    def fake_final_plan(*, release_dir, runs_dir, regression_manifest_path=None):
        assert release_dir == tmp_path / "release"
        assert runs_dir == tmp_path / "runs"
        assert regression_manifest_path == manifest_path
        return {
            "schema_version": 1,
            "overall_status": "action_required",
            "action_count": 1,
            "proof_boundary": "A final plan is not evidence.",
            "next_action": {
                "section_id": "physical_validation",
                "section_label": "Physical validation",
                "action_id": "pla",
                "label": "PLA",
                "status": "recorded_but_not_passed",
                "detail": "no passed physical evidence",
                "command": "printpipe record-physical-evidence runs/pla",
                "command_kind": "record_command",
                "coupon_stl_path": "runs/pla/40_geometry/coupon.stl",
            },
        }

    monkeypatch.setattr(
        "printpipe.final_plan.build_final_action_plan",
        fake_final_plan,
    )

    exit_code = main(
        [
            "final-next",
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
    assert payload["next_action"]["action_id"] == "pla"
    assert payload["next_action"]["coupon_stl_path"].endswith("coupon.stl")
