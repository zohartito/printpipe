from __future__ import annotations

import json
import sys
from pathlib import Path

from printpipe.beta.failures import build_failure_report, write_failure_report_files
from printpipe.beta.feedback import (
    build_trusted_user_feedback,
    write_trusted_user_feedback_files,
)
from printpipe.beta.rule_updates import build_rule_update, write_rule_update_files
from printpipe.beta.regression import (
    ExpectedOutcome,
    RegressionCase,
    RegressionManifest,
    write_regression_manifest,
)
from printpipe.beta.beta_plan import (
    BETA_PLAN_PROOF_BOUNDARY,
    build_beta_action_plan,
    render_beta_action_plan,
)
from printpipe.cli import main


def test_beta_action_plan_reports_missing_beta_evidence(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"

    plan = build_beta_action_plan(runs_dir)

    assert plan["overall_status"] == "action_required"
    assert plan["runs_dir"] == str(runs_dir.resolve())
    assert plan["proof_boundary"] == BETA_PLAN_PROOF_BOUNDARY
    assert plan["evidence"]["failure_report_count"] == 0
    assert plan["evidence"]["failure_regression_status"]["overall_status"] == "no_failures"
    assert plan["evidence"]["rule_update_status"]["overall_status"] == "missing"
    assert plan["evidence"]["trusted_feedback_status"]["unique_trusted_user_count"] == 0
    assert plan["evidence"]["regression_status"]["overall_status"] == "not_configured"
    assert plan["evidence"]["dogfood_status"]["overall_status"] == "missing"
    actions = {action["id"]: action for action in plan["actions"]}
    assert actions["run_beta_dogfood"]["status"] == "action_required"
    assert "slipper" in actions["run_beta_dogfood"]["detail"].lower()
    assert actions["physical_validation"]["status"] == "action_required"
    assert actions["physical_validation"]["command"] == (
        f'printpipe physical-plan --runs-dir "{runs_dir.resolve()}"'
    )
    assert actions["record_beta_failure"]["status"] == "waiting_for_evidence"
    assert "printpipe record-beta-failure" in actions["record_beta_failure"]["command"]
    assert actions["run_regressions"]["status"] == "action_required"
    assert "record-beta-failure" in actions["run_regressions"]["detail"]
    assert actions["update_rules"]["status"] == "waiting_for_evidence"
    assert "record-rule-update" in actions["update_rules"]["command"]
    assert actions["trusted_user_beta"]["status"] == "action_required"
    assert "0 / 3 trusted users completed feedback" in actions["trusted_user_beta"]["detail"]
    assert "recorded feedback" not in actions["trusted_user_beta"]["detail"]
    trusted_command = actions["trusted_user_beta"]["command"]
    assert '--outcome "<passed|failed|partial>"' in trusted_command
    assert '--would-print "<yes|no|unknown>"' in trusted_command
    assert '--recommendation "<recommendation>"' in trusted_command
    assert "--outcome passed" not in trusted_command
    assert "--would-print no" not in trusted_command
    assert "--recommendation needs_review" not in trusted_command


def test_beta_action_plan_marks_dogfood_ready_from_software_evidence(
    tmp_path: Path,
) -> None:
    runs_dir = tmp_path / "runs"
    _write_software_dogfood_run(
        runs_dir / "20260528-slipper-wide-upper",
        source_path="/proof/slipper_size11_wide_upper.stl",
        slice_status="skipped",
        extra_stage_names=("validation.flex_coupon",),
    )
    _write_software_dogfood_run(
        runs_dir / "dogfood" / "20260528-simple-figurine-ascii",
        source_path="/fixtures/simple_figurine_ascii.stl",
    )
    _write_software_dogfood_run(
        runs_dir / "dogfood" / "20260528-cup-vase-open-frustum",
        source_path="/fixtures/cup_vase_open_frustum.stl",
    )
    _write_software_dogfood_run(
        runs_dir / "dogfood" / "20260528-flat-bracket",
        source_path="/fixtures/flat_bracket.stl",
    )

    plan = build_beta_action_plan(runs_dir)

    status = plan["evidence"]["dogfood_status"]
    actions = {action["id"]: action for action in plan["actions"]}
    assert status["overall_status"] == "passed"
    assert status["slipper_status"] == "passed"
    assert status["non_slipper_passed_count"] == 3
    assert status["required_non_slipper_count"] == 3
    assert actions["run_beta_dogfood"]["status"] == "ready"
    assert "slipper software run" in actions["run_beta_dogfood"]["detail"]
    assert "3 / 3 non-slipper" in actions["run_beta_dogfood"]["detail"]
    assert actions["run_beta_dogfood"]["command"] == ""


def test_beta_action_plan_keeps_dogfood_action_required_until_matrix_is_complete(
    tmp_path: Path,
) -> None:
    runs_dir = tmp_path / "runs"
    _write_software_dogfood_run(
        runs_dir / "20260528-slipper-wide-upper",
        source_path="/proof/slipper_size11_wide_upper.stl",
        slice_status="skipped",
        extra_stage_names=("validation.flex_coupon",),
    )
    _write_software_dogfood_run(
        runs_dir / "dogfood" / "20260528-simple-figurine-ascii",
        source_path="/fixtures/simple_figurine_ascii.stl",
    )
    _write_software_dogfood_run(
        runs_dir / "dogfood" / "20260528-cup-vase-open-frustum",
        source_path="/fixtures/cup_vase_open_frustum.stl",
    )

    plan = build_beta_action_plan(runs_dir)

    status = plan["evidence"]["dogfood_status"]
    actions = {action["id"]: action for action in plan["actions"]}
    assert status["overall_status"] == "incomplete"
    assert status["slipper_status"] == "passed"
    assert status["non_slipper_passed_count"] == 2
    assert actions["run_beta_dogfood"]["status"] == "action_required"
    assert "2 / 3 non-slipper" in actions["run_beta_dogfood"]["detail"]


def test_beta_action_plan_detects_failure_packets_and_regression_manifest(
    tmp_path: Path,
) -> None:
    runs_dir = tmp_path / "runs"
    run_root = runs_dir / "run-beta-001"
    run_root.mkdir(parents=True)
    report = build_failure_report(
        run_id="run-beta-001",
        input_type="existing_stl",
        material="SUNLU TPU 90A",
        printer="Bambu Lab P2S",
        failed_stage="slice",
        symptoms=("floating cantilever warning",),
        artifacts=(),
        reproduction_command="printpipe run 00_input/part.stl --material tpu",
        physical_print_status="not_printed",
    )
    write_failure_report_files(run_root=run_root, report=report)
    manifest_path = tmp_path / "regressions" / "beta_regressions.json"
    manifest_path.parent.mkdir(parents=True)
    write_regression_manifest(
        RegressionManifest(
            cases=(
                RegressionCase(
                    case_id="known-success",
                    source_run_id="run-beta-001",
                    fixture_path=Path("fixtures/good.stl"),
                    command=(sys.executable, "-c", "print('ok')"),
                    expected=ExpectedOutcome.SUCCESS,
                    notes="Captured from beta triage.",
                ),
            )
        ),
        manifest_path,
    )

    plan = build_beta_action_plan(
        runs_dir,
        regression_manifest_path=manifest_path,
    )

    actions = {action["id"]: action for action in plan["actions"]}
    assert plan["evidence"]["failure_report_count"] == 1
    assert plan["evidence"]["failure_reports"][0]["run_id"] == "run-beta-001"
    assert plan["evidence"]["regression_status"]["overall_status"] == "passed"
    assert plan["evidence"]["failure_regression_status"]["overall_status"] == "passed"
    assert plan["evidence"]["regression_status"]["case_count"] == 1
    assert actions["record_beta_failure"]["status"] == "ready"
    assert actions["run_regressions"]["status"] == "ready"
    assert actions["run_regressions"]["command"] == (
        f'printpipe run-regressions "{manifest_path.resolve()}" --strict'
    )
    assert actions["update_rules"]["status"] == "action_required"
    assert "material/orientation/repair" in actions["update_rules"]["detail"]
    assert "record-rule-update" in actions["update_rules"]["command"]


def test_beta_action_plan_marks_rule_updates_ready_after_verified_packets(
    tmp_path: Path,
) -> None:
    runs_dir = tmp_path / "runs"
    for rule_type in ("material", "orientation", "repair"):
        run_root = runs_dir / f"run-{rule_type}"
        run_root.mkdir(parents=True)
        write_rule_update_files(
            run_root=run_root,
            update=build_rule_update(
                run_id=run_root.name,
                rule_type=rule_type,
                status="verified",
                summary=f"Verified {rule_type} update.",
                source="beta triage",
                changed_files=(f"src/printpipe/{rule_type}.py",),
                tests=(f"tests/test_{rule_type}.py",),
            ),
        )

    plan = build_beta_action_plan(runs_dir)

    actions = {action["id"]: action for action in plan["actions"]}
    assert plan["evidence"]["rule_update_status"]["overall_status"] == "passed"
    assert actions["update_rules"]["status"] == "ready"
    assert "Material, orientation, and repair" in actions["update_rules"]["detail"]


def test_beta_action_plan_marks_trusted_user_beta_ready_after_three_users(
    tmp_path: Path,
) -> None:
    runs_dir = tmp_path / "runs"
    _write_feedback(runs_dir / "run-maya", tester="Maya")
    _write_feedback(runs_dir / "run-sam", tester="Sam", outcome="failed")
    _write_feedback(runs_dir / "run-lee", tester="Lee", outcome="partial")

    plan = build_beta_action_plan(runs_dir)

    actions = {action["id"]: action for action in plan["actions"]}
    status = plan["evidence"]["trusted_feedback_status"]
    assert status["overall_status"] == "passed"
    assert status["trusted_users"] == ["Lee", "Maya", "Sam"]
    assert actions["trusted_user_beta"]["status"] == "ready"
    assert "3 / 3 trusted users completed feedback" in actions["trusted_user_beta"]["detail"]


def test_render_beta_action_plan_lists_actions_and_boundary(tmp_path: Path) -> None:
    plan = build_beta_action_plan(tmp_path / "runs")

    text = render_beta_action_plan(plan)

    assert "PrintPipe Beta Action Plan" in text
    assert "overall: action_required" in text
    assert BETA_PLAN_PROOF_BOUNDARY in text
    assert "run_beta_dogfood" in text
    assert "printpipe physical-plan" in text
    assert "trusted_user_beta" in text


def test_cli_beta_plan_prints_json(tmp_path: Path, capsys) -> None:
    runs_dir = tmp_path / "runs"

    exit_code = main(["beta-plan", "--runs-dir", str(runs_dir), "--json"])

    payload = json.loads(capsys.readouterr().out)
    actions = {action["id"]: action for action in payload["actions"]}
    assert exit_code == 0
    assert payload["overall_status"] == "action_required"
    assert payload["evidence"]["failure_report_count"] == 0
    assert actions["physical_validation"]["command"] == (
        f'printpipe physical-plan --runs-dir "{runs_dir.resolve()}"'
    )


def test_cli_beta_plan_uses_standard_regression_manifest_when_present(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    manifest_path = tmp_path / "regressions" / "dogfood_failures.json"
    manifest_path.parent.mkdir()
    manifest_path.write_text('{"schema_version": 1, "cases": []}\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    def fake_beta_plan(runs_dir, *, regression_manifest_path=None):
        assert regression_manifest_path == manifest_path
        return {
            "schema_version": 1,
            "overall_status": "action_required",
            "actions": [],
        }

    monkeypatch.setattr(
        "printpipe.beta.beta_plan.build_beta_action_plan",
        fake_beta_plan,
    )

    exit_code = main(["beta-plan", "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["overall_status"] == "action_required"


def _write_feedback(
    run_root: Path,
    *,
    tester: str,
    outcome: str = "passed",
) -> None:
    run_root.mkdir(parents=True)
    report = run_root / "80_reports" / "run_report.html"
    report.parent.mkdir(parents=True)
    report.write_text("<h1>run report</h1>\n", encoding="utf-8")
    feedback = build_trusted_user_feedback(
        run_id=run_root.name,
        tester=tester,
        tester_type="trusted_user",
        input_type="existing_stl",
        material="Bambu PLA Basic",
        printer="Bambu Lab P2S",
        outcome=outcome,
        summary=f"{tester} completed a beta run.",
        issues=(),
        would_print="no",
        recommendation="needs_review",
        artifacts=(),
    )
    write_trusted_user_feedback_files(run_root=run_root, feedback=feedback)


def _write_software_dogfood_run(
    run_root: Path,
    *,
    source_path: str,
    slice_status: str = "succeeded",
    extra_stage_names: tuple[str, ...] = (),
) -> None:
    run_root.mkdir(parents=True)
    input_name = Path(source_path).name
    (run_root / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "run_id": run_root.name,
                "input": {
                    "kind": "mesh",
                    "source_path": source_path,
                    "stored_path": f"00_input/{input_name}",
                },
            }
        ),
        encoding="utf-8",
    )
    stages = [
        {"stage": "meshgen", "status": "succeeded", "message": "imported mesh"},
        {"stage": "mesh_repair", "status": "succeeded", "message": "repaired mesh"},
        {"stage": "bundle", "status": "succeeded", "message": "wrote bundle"},
        {
            "stage": "bundle_validation",
            "status": "succeeded",
            "message": "validated bundle",
        },
    ]
    for stage_name in extra_stage_names:
        stages.append(
            {
                "stage": stage_name,
                "status": "succeeded",
                "message": f"{stage_name} succeeded",
            }
        )
    stages.append(
        {
            "stage": "slice",
            "status": slice_status,
            "message": "slice result recorded",
        }
    )
    reports_dir = run_root / "80_reports"
    reports_dir.mkdir(parents=True)
    (reports_dir / "run_report.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "run_id": run_root.name,
                "warnings": [],
                "stages": stages,
            }
        ),
        encoding="utf-8",
    )
    if slice_status == "succeeded":
        slice_dir = run_root / "70_slice"
        slice_dir.mkdir(parents=True)
        (slice_dir / "slice_result.json").write_text(
            json.dumps({"return_code": 0, "warnings": [], "errors": []}),
            encoding="utf-8",
        )
    if extra_stage_names:
        geometry_dir = run_root / "40_geometry"
        geometry_dir.mkdir(parents=True)
        (geometry_dir / "flex_coupon_40x15x3.stl").write_text(
            "solid coupon\nendsolid coupon\n",
            encoding="utf-8",
        )
