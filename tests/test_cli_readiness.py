from __future__ import annotations

import json
from pathlib import Path

from printpipe.cli import build_parser, main


def test_readiness_parser_accepts_runs_dir_json_and_strict_flags(tmp_path: Path) -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "readiness",
            "--runs-dir",
            str(tmp_path / "runs"),
            "--regression-manifest",
            str(tmp_path / "regression_manifest.json"),
            "--json",
            "--strict",
        ]
    )

    assert args.command == "readiness"
    assert args.runs_dir == tmp_path / "runs"
    assert args.regression_manifest == tmp_path / "regression_manifest.json"
    assert args.json is True
    assert args.strict is True


def test_readiness_prints_json_and_can_gate_strictly(monkeypatch, tmp_path: Path, capsys) -> None:
    def fake_report(runs_dir, *, regression_manifest_path=None):
        assert regression_manifest_path == tmp_path / "regression_manifest.json"
        return {
            "schema_version": 1,
            "overall_status": "action_required",
            "action_required_count": 1,
            "gates": [
                {
                    "id": "physical_validation",
                    "label": "Physical validation",
                    "status": "action_required",
                    "detail": "Missing passed physical evidence.",
                    "action": "Print coupons.",
                }
            ],
        }

    monkeypatch.setattr(
        "printpipe.beta.readiness.build_beta_readiness_report",
        fake_report,
    )

    exit_code = main(
        [
            "readiness",
            "--runs-dir",
            str(tmp_path / "runs"),
            "--regression-manifest",
            str(tmp_path / "regression_manifest.json"),
            "--json",
            "--strict",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert payload["overall_status"] == "action_required"
    assert payload["gates"][0]["id"] == "physical_validation"


def test_readiness_does_not_auto_execute_standard_regression_manifest(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    manifest_path = tmp_path / "regressions" / "dogfood_failures.json"
    manifest_path.parent.mkdir()
    manifest_path.write_text('{"schema_version": 1, "cases": []}\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    def fake_report(runs_dir, *, regression_manifest_path=None):
        assert regression_manifest_path is None
        return {
            "schema_version": 1,
            "overall_status": "ready",
            "action_required_count": 0,
            "gates": [],
        }

    monkeypatch.setattr(
        "printpipe.beta.readiness.build_beta_readiness_report",
        fake_report,
    )

    exit_code = main(["readiness", "--runs-dir", "runs", "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["overall_status"] == "ready"


def test_readiness_keeps_regression_manifest_optional_when_standard_file_is_absent(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_report(runs_dir, *, regression_manifest_path=None):
        assert regression_manifest_path is None
        return {
            "schema_version": 1,
            "overall_status": "ready",
            "action_required_count": 0,
            "gates": [],
        }

    monkeypatch.setattr(
        "printpipe.beta.readiness.build_beta_readiness_report",
        fake_report,
    )

    exit_code = main(["readiness", "--runs-dir", "runs", "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["overall_status"] == "ready"


def test_readiness_prints_human_gate_summary(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(
        "printpipe.beta.readiness.build_beta_readiness_report",
        lambda runs_dir, *, regression_manifest_path=None: {
            "schema_version": 1,
            "overall_status": "ready",
            "action_required_count": 0,
            "gates": [
                {
                    "id": "dependencies",
                    "label": "Dependencies",
                    "status": "ready",
                    "detail": "Required dependencies are available.",
                    "action": "No action needed.",
                }
            ],
        },
    )

    exit_code = main(["readiness", "--runs-dir", str(tmp_path / "runs")])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "PrintPipe Readiness" in captured.out
    assert "overall: ready" in captured.out
    assert "- ready: Dependencies - Required dependencies are available." in captured.out
