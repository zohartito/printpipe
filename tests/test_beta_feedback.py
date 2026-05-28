from __future__ import annotations

import json
from pathlib import Path

from printpipe.beta.feedback import (
    TRUSTED_FEEDBACK_REQUIRED_HEADINGS,
    FeedbackArtifact,
    build_trusted_user_feedback_plan,
    build_trusted_user_feedback,
    build_trusted_user_feedback_status,
    missing_required_feedback_headings,
    render_trusted_user_feedback_plan,
    render_trusted_user_feedback_status,
    write_trusted_user_feedback_files,
)
from printpipe.cli import main


def test_trusted_user_feedback_writes_json_markdown_and_copies_artifacts(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "runs" / "run-trusted-001"
    report = run_root / "80_reports" / "run_report.html"
    report.parent.mkdir(parents=True)
    report.write_text("<h1>report</h1>\n", encoding="utf-8")
    feedback = build_trusted_user_feedback(
        run_id="run-trusted-001",
        tester="Maya",
        tester_type="trusted_user",
        input_type="existing_stl",
        material="Bambu PLA Basic",
        printer="Bambu Lab P2S",
        outcome="passed",
        summary="Run completed and the report made sense.",
        issues=(),
        would_print="no",
        recommendation="needs_review",
        artifacts=(FeedbackArtifact(label="HTML report", path=report, kind="report"),),
    )

    result = write_trusted_user_feedback_files(
        run_root=run_root,
        feedback=feedback,
        copy_artifacts=True,
    )

    json_path = run_root / "90_beta" / "trusted_user_feedback.json"
    markdown_path = run_root / "90_beta" / "trusted_user_feedback.md"
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")

    assert result["json_path"] == str(json_path)
    assert result["markdown_path"] == str(markdown_path)
    assert result["missing_required_headings"] == []
    assert payload["tester"] == "Maya"
    assert payload["tester_type"] == "trusted_user"
    assert payload["outcome"] == "passed"
    assert payload["would_print"] == "no"
    assert payload["recommendation"] == "needs_review"
    assert payload["artifacts"][0]["path"] == "90_beta/artifacts/run_report.html"
    assert (run_root / "90_beta" / "artifacts" / "run_report.html").read_text(
        encoding="utf-8"
    ) == "<h1>report</h1>\n"
    assert missing_required_feedback_headings(markdown) == []
    for heading in TRUSTED_FEEDBACK_REQUIRED_HEADINGS:
        assert f"## {heading}" in markdown


def test_trusted_user_feedback_status_requires_three_unique_trusted_users(
    tmp_path: Path,
) -> None:
    runs_dir = tmp_path / "runs"
    _write_feedback(runs_dir / "run-internal", tester="Zohar", tester_type="internal")
    _write_feedback(runs_dir / "run-maya", tester="Maya")
    _write_feedback(runs_dir / "run-maya-second", tester="Maya")
    _write_feedback(runs_dir / "run-sam", tester="Sam", outcome="failed")

    status = build_trusted_user_feedback_status(runs_dir)

    assert status["overall_status"] == "insufficient_feedback"
    assert status["packet_count"] == 4
    assert status["trusted_user_packet_count"] == 3
    assert status["unique_trusted_user_count"] == 2
    assert status["required_trusted_user_count"] == 3
    assert status["missing_trusted_user_count"] == 1
    assert status["outcome_counts"]["passed"] == 3
    assert status["outcome_counts"]["failed"] == 1

    _write_feedback(runs_dir / "run-lee", tester="Lee", outcome="partial")

    passed = build_trusted_user_feedback_status(runs_dir)

    assert passed["overall_status"] == "passed"
    assert passed["unique_trusted_user_count"] == 3
    assert passed["missing_trusted_user_count"] == 0
    assert passed["trusted_users"] == ["Lee", "Maya", "Sam"]


def test_trusted_user_feedback_status_does_not_count_not_run_as_completed_feedback(
    tmp_path: Path,
) -> None:
    runs_dir = tmp_path / "runs"
    _write_feedback(runs_dir / "run-maya", tester="Maya")
    _write_feedback(runs_dir / "run-sam", tester="Sam", outcome="failed")
    _write_feedback(runs_dir / "run-lee-not-run", tester="Lee", outcome="not_run")

    status = build_trusted_user_feedback_status(runs_dir)

    assert status["overall_status"] == "insufficient_feedback"
    assert status["trusted_user_packet_count"] == 3
    assert status["completed_trusted_user_count"] == 2
    assert status["unique_trusted_user_count"] == 2
    assert status["missing_trusted_user_count"] == 1
    assert status["trusted_users"] == ["Maya", "Sam"]
    assert status["not_run_trusted_users"] == ["Lee"]


def test_render_trusted_user_feedback_status_names_missing_count(tmp_path: Path) -> None:
    status = build_trusted_user_feedback_status(tmp_path / "runs")

    text = render_trusted_user_feedback_status(status)

    assert "PrintPipe Trusted-User Feedback" in text
    assert "overall: insufficient_feedback" in text
    assert "trusted users: 0 / 3" in text


def test_trusted_user_feedback_plan_lists_missing_tester_actions(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    _write_feedback(runs_dir / "run-maya", tester="Maya")
    _write_feedback(runs_dir / "run-sam", tester="Sam", outcome="failed")

    plan = build_trusted_user_feedback_plan(runs_dir)

    assert plan["overall_status"] == "action_required"
    assert plan["trusted_user_count"] == 2
    assert plan["required_trusted_user_count"] == 3
    assert plan["action_count"] == 1
    assert plan["trusted_users"] == ["Maya", "Sam"]
    assert "not trusted-user evidence" in plan["proof_boundary"]
    action = plan["actions"][0]
    assert action["slot"] == 3
    assert action["status"] == "action_required"
    assert "record-beta-feedback" in action["record_command"]
    assert "--tester" in action["record_command"]
    assert "--outcome passed" in action["record_command"]
    assert "runs/<run-id>" in action["record_command"]


def test_trusted_user_feedback_plan_ignores_not_run_packets(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    _write_feedback(runs_dir / "run-maya", tester="Maya")
    _write_feedback(runs_dir / "run-sam", tester="Sam", outcome="failed")
    _write_feedback(runs_dir / "run-lee-not-run", tester="Lee", outcome="not_run")

    plan = build_trusted_user_feedback_plan(runs_dir)

    assert plan["overall_status"] == "action_required"
    assert plan["trusted_user_count"] == 2
    assert plan["trusted_users"] == ["Maya", "Sam"]
    assert plan["missing_trusted_user_count"] == 1
    assert plan["action_count"] == 1
    assert plan["actions"][0]["slot"] == 3


def test_trusted_user_feedback_plan_ready_after_three_users(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    _write_feedback(runs_dir / "run-maya", tester="Maya")
    _write_feedback(runs_dir / "run-sam", tester="Sam", outcome="failed")
    _write_feedback(runs_dir / "run-lee", tester="Lee", outcome="partial")

    plan = build_trusted_user_feedback_plan(runs_dir)

    assert plan["overall_status"] == "ready"
    assert plan["action_count"] == 0
    assert plan["actions"] == []


def test_render_trusted_user_feedback_plan_names_actions(tmp_path: Path) -> None:
    plan = build_trusted_user_feedback_plan(tmp_path / "runs")

    text = render_trusted_user_feedback_plan(plan)

    assert "PrintPipe Trusted-User Feedback Plan" in text
    assert "overall: action_required" in text
    assert "trusted users: 0 / 3" in text
    assert "record-beta-feedback" in text
    assert "not trusted-user evidence" in text


def test_cli_record_beta_feedback_and_status(tmp_path: Path, capsys) -> None:
    run_root = tmp_path / "runs" / "run-trusted-001"
    report = run_root / "80_reports" / "run_report.html"
    report.parent.mkdir(parents=True)
    report.write_text("<h1>report</h1>\n", encoding="utf-8")

    exit_code = main(
        [
            "record-beta-feedback",
            str(run_root),
            "--tester",
            "Maya",
            "--input-type",
            "existing_stl",
            "--material",
            "Bambu PLA Basic",
            "--printer",
            "Bambu Lab P2S",
            "--outcome",
            "passed",
            "--summary",
            "Run completed and report made sense.",
            "--would-print",
            "no",
            "--recommendation",
            "needs_review",
            "--artifact",
            f"HTML report|report|{report}|User inspected report",
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["json_path"].endswith("90_beta/trusted_user_feedback.json")
    assert payload["missing_required_headings"] == []

    status_exit = main(
        [
            "beta-feedback-status",
            "--runs-dir",
            str(tmp_path / "runs"),
            "--json",
            "--strict",
        ]
    )
    status_payload = json.loads(capsys.readouterr().out)

    assert status_exit == 2
    assert status_payload["overall_status"] == "insufficient_feedback"
    assert status_payload["unique_trusted_user_count"] == 1


def test_cli_beta_feedback_plan_prints_json(tmp_path: Path, capsys) -> None:
    runs_dir = tmp_path / "runs"

    exit_code = main(["beta-feedback-plan", "--runs-dir", str(runs_dir), "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["overall_status"] == "action_required"
    assert payload["action_count"] == 3
    assert payload["actions"][0]["slot"] == 1
    assert "record-beta-feedback" in payload["actions"][0]["record_command"]


def _write_feedback(
    run_root: Path,
    *,
    tester: str,
    tester_type: str = "trusted_user",
    outcome: str = "passed",
) -> None:
    run_root.mkdir(parents=True)
    feedback = build_trusted_user_feedback(
        run_id=run_root.name,
        tester=tester,
        tester_type=tester_type,
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
