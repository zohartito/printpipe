"""Action plan helpers for remaining beta evidence and triage work."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from printpipe.beta.physical_status import build_physical_validation_status
from printpipe.beta.regression import run_regression_manifest

BETA_PLAN_PROOF_BOUNDARY = (
    "A generated beta plan is not trusted-user evidence, physical print proof, "
    "or a material/orientation/repair rule update until those results are recorded."
)


def build_beta_action_plan(
    runs_dir: str | Path,
    *,
    regression_manifest_path: str | Path | None = None,
    physical_status: Mapping[str, Any] | None = None,
    regression_status: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return beta next actions from recorded evidence on disk."""

    runs_root = Path(runs_dir).expanduser().resolve()
    failures = _load_failure_reports(runs_root)
    physical = (
        dict(physical_status)
        if physical_status is not None
        else build_physical_validation_status(runs_root)
    )
    regression = _build_regression_status(
        regression_status=regression_status,
        regression_manifest_path=regression_manifest_path,
    )
    manifest_path = (
        Path(regression_manifest_path).expanduser().resolve()
        if regression_manifest_path is not None
        else None
    )
    actions = [
        _dogfood_action(),
        _physical_action(physical, runs_dir=runs_root),
        _failure_capture_action(failures),
        _regression_action(regression, regression_manifest_path=manifest_path),
        _trusted_user_action(),
        _rules_action(failures),
    ]
    action_required_count = sum(
        1 for action in actions if action["status"] == "action_required"
    )
    return {
        "schema_version": 1,
        "runs_dir": str(runs_root),
        "overall_status": "action_required" if action_required_count else "ready",
        "action_required_count": action_required_count,
        "proof_boundary": BETA_PLAN_PROOF_BOUNDARY,
        "evidence": {
            "failure_report_count": len(failures),
            "failure_reports": failures,
            "physical_status": physical,
            "regression_manifest_path": str(manifest_path) if manifest_path else "",
            "regression_status": regression,
        },
        "actions": actions,
    }


def render_beta_action_plan(plan: Mapping[str, Any]) -> str:
    """Render a human-readable beta action plan."""

    lines = [
        "PrintPipe Beta Action Plan",
        f"runs dir: {plan.get('runs_dir', 'unknown')}",
        f"overall: {plan.get('overall_status', 'unknown')}",
        f"action required: {plan.get('action_required_count', 0)}",
        "",
        str(plan.get("proof_boundary", BETA_PLAN_PROOF_BOUNDARY)),
        "",
        "Actions:",
    ]
    actions = plan.get("actions")
    if not isinstance(actions, list) or not actions:
        lines.append("- no beta actions required")
        lines.append("")
        return "\n".join(lines)

    for action in actions:
        item = _dict(action)
        lines.append(
            f"- {item.get('status', 'unknown')}: "
            f"{item.get('id', 'unknown')} - {item.get('label', '')}"
        )
        detail = str(item.get("detail") or "")
        if detail:
            lines.append(f"  detail: {detail}")
        command = str(item.get("command") or "")
        if command:
            lines.append(f"  command: {command}")
    lines.append("")
    return "\n".join(lines)


def _dogfood_action() -> dict[str, str]:
    return {
        "id": "run_beta_dogfood",
        "label": "Dogfood canonical object matrix",
        "status": "action_required",
        "detail": (
            "Run the slipper proof plus at least three non-slipper objects through "
            "the current pipeline and record the outcomes."
        ),
        "command": "printpipe run <input.stl|image|prompt> --material <material> --slice",
    }


def _physical_action(
    physical_status: Mapping[str, Any],
    *,
    runs_dir: Path,
) -> dict[str, str]:
    if physical_status.get("overall_status") == "passed":
        return {
            "id": "physical_validation",
            "label": "Physical material validation",
            "status": "ready",
            "detail": "Required PLA/PETG/TPU physical evidence has passed.",
            "command": "",
        }
    return {
        "id": "physical_validation",
        "label": "Physical material validation",
        "status": "action_required",
        "detail": (
            "PLA/PETG/TPU physical evidence is incomplete; generate exact "
            "family-specific printer-side actions."
        ),
        "command": f"printpipe physical-plan --runs-dir {_quote(str(runs_dir))}",
    }


def _failure_capture_action(failure_reports: list[dict[str, Any]]) -> dict[str, str]:
    if failure_reports:
        return {
            "id": "record_beta_failure",
            "label": "Capture failed beta runs",
            "status": "ready",
            "detail": f"{len(failure_reports)} beta failure packet(s) found.",
            "command": "printpipe record-beta-failure <run-root> ...",
        }
    return {
        "id": "record_beta_failure",
        "label": "Capture failed beta runs",
        "status": "waiting_for_evidence",
        "detail": (
            "No beta failure packets are recorded yet; when a run fails, preserve "
            "the context and optionally seed a regression manifest."
        ),
        "command": (
            'printpipe record-beta-failure "<run-root>" --input-type existing_stl '
            '--material "<material>" --printer "Bambu Lab P2S" '
            '--failed-stage "<stage>" --symptom "<symptom>" '
            '--reproduction-command "printpipe run <input> --material <material>" '
            '--physical-print-status not_printed '
            '--regression-manifest "regressions/beta_regressions.json"'
        ),
    }


def _regression_action(
    regression_status: Mapping[str, Any],
    *,
    regression_manifest_path: Path | None,
) -> dict[str, str]:
    overall = str(regression_status.get("overall_status") or "not_configured")
    case_count = int(regression_status.get("case_count") or 0)
    if overall == "passed" and case_count > 0 and regression_manifest_path is not None:
        return {
            "id": "run_regressions",
            "label": "Replay captured regressions",
            "status": "ready",
            "detail": f"{case_count} regression case(s) match expected outcomes.",
            "command": (
                "printpipe run-regressions "
                f"{_quote(str(regression_manifest_path))} --strict"
            ),
        }
    if regression_manifest_path is None:
        return {
            "id": "run_regressions",
            "label": "Replay captured regressions",
            "status": "action_required",
            "detail": (
                "No regression manifest is configured; capture a beta failure with "
                "record-beta-failure or pass --regression-manifest."
            ),
            "command": 'printpipe run-regressions "regressions/beta_regressions.json" --strict',
        }
    if overall == "passed" and case_count == 0:
        detail = "Regression manifest has no cases; seed it from captured beta failures."
    elif overall == "missing":
        detail = "Regression manifest path was provided but the file does not exist."
    else:
        failed_count = int(regression_status.get("failed_count") or 0)
        detail = f"{failed_count} regression case(s) drifted from expected outcomes."
    return {
        "id": "run_regressions",
        "label": "Replay captured regressions",
        "status": "action_required",
        "detail": detail,
        "command": (
            "printpipe run-regressions "
            f"{_quote(str(regression_manifest_path))} --strict"
        ),
    }


def _trusted_user_action() -> dict[str, str]:
    return {
        "id": "trusted_user_beta",
        "label": "Trusted-user beta",
        "status": "action_required",
        "detail": (
            "Give the app to 3 to 5 trusted users and collect their successful "
            "and failed run packets before calling beta complete."
        ),
        "command": "",
    }


def _rules_action(failure_reports: list[dict[str, Any]]) -> dict[str, str]:
    if failure_reports:
        return {
            "id": "update_rules",
            "label": "Update material/orientation/repair rules",
            "status": "action_required",
            "detail": (
                "Review captured failures and patch material/orientation/repair "
                "rules when the same cause repeats."
            ),
            "command": "",
        }
    return {
        "id": "update_rules",
        "label": "Update material/orientation/repair rules",
        "status": "waiting_for_evidence",
        "detail": (
            "No captured beta failures exist yet, so rule changes would be guesses."
        ),
        "command": "",
    }


def _build_regression_status(
    *,
    regression_status: Mapping[str, Any] | None,
    regression_manifest_path: str | Path | None,
) -> dict[str, Any]:
    if regression_status is not None:
        return dict(regression_status)
    if regression_manifest_path is None:
        return {"overall_status": "not_configured", "case_count": 0}
    path = Path(regression_manifest_path).expanduser().resolve()
    if not path.exists():
        return {
            "overall_status": "missing",
            "manifest_path": str(path),
            "case_count": 0,
            "passed_count": 0,
            "failed_count": 0,
        }
    try:
        return run_regression_manifest(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {
            "overall_status": "failed",
            "manifest_path": str(path),
            "case_count": 0,
            "passed_count": 0,
            "failed_count": 1,
            "error": str(exc),
        }


def _load_failure_reports(runs_dir: Path) -> list[dict[str, Any]]:
    if not runs_dir.exists():
        return []
    reports: list[dict[str, Any]] = []
    for report_path in sorted(runs_dir.glob("*/90_beta/failure_report.json")):
        try:
            payload = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        reports.append(_failure_summary(payload, report_path=report_path))
    return reports


def _failure_summary(
    payload: Mapping[str, Any],
    *,
    report_path: Path,
) -> dict[str, Any]:
    run_root = report_path.parents[1]
    markdown_path = report_path.with_suffix(".md")
    return {
        "run_id": str(payload.get("run_id") or run_root.name),
        "run_root": str(run_root),
        "json_path": str(report_path),
        "markdown_path": str(markdown_path) if markdown_path.exists() else "",
        "input_type": str(payload.get("input_type") or ""),
        "material": str(payload.get("material") or ""),
        "printer": str(payload.get("printer") or ""),
        "failed_stage": str(payload.get("failed_stage") or ""),
        "symptom_count": len(_list(payload.get("symptoms"))),
        "artifact_count": len(_list(payload.get("artifacts"))),
        "physical_print_status": str(payload.get("physical_print_status") or ""),
    }


def _quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


__all__ = [
    "BETA_PLAN_PROOF_BOUNDARY",
    "build_beta_action_plan",
    "render_beta_action_plan",
]
