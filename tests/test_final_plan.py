from __future__ import annotations

import json
from pathlib import Path

from printpipe.cli import build_parser, main
from printpipe.final_plan import build_final_action_plan, render_final_action_plan


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
