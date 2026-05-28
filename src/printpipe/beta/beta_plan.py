"""Action plan helpers for remaining beta evidence and triage work."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from printpipe.beta.feedback import build_trusted_user_feedback_status
from printpipe.beta.physical_status import build_physical_validation_status
from printpipe.beta.regression import (
    build_failure_regression_status,
    run_regression_manifest,
)
from printpipe.beta.rule_updates import build_rule_update_status

BETA_PLAN_PROOF_BOUNDARY = (
    "A generated beta plan is not trusted-user evidence, physical print proof, "
    "or a material/orientation/repair rule update until those results are recorded."
)


def build_beta_action_plan(
    runs_dir: str | Path,
    *,
    regression_manifest_path: str | Path | None = None,
    dogfood_status: Mapping[str, Any] | None = None,
    physical_status: Mapping[str, Any] | None = None,
    trusted_feedback_status: Mapping[str, Any] | None = None,
    rule_update_status: Mapping[str, Any] | None = None,
    failure_regression_status: Mapping[str, Any] | None = None,
    regression_status: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return beta next actions from recorded evidence on disk."""

    runs_root = Path(runs_dir).expanduser().resolve()
    failures = _load_failure_reports(runs_root)
    dogfood = (
        dict(dogfood_status)
        if dogfood_status is not None
        else _build_dogfood_software_status(runs_root)
    )
    physical = (
        dict(physical_status)
        if physical_status is not None
        else build_physical_validation_status(runs_root)
    )
    regression = _build_regression_status(
        regression_status=regression_status,
        regression_manifest_path=regression_manifest_path,
    )
    failure_regressions = (
        dict(failure_regression_status)
        if failure_regression_status is not None
        else build_failure_regression_status(
            runs_root,
            regression_manifest_path=regression_manifest_path,
        )
    )
    trusted_feedback = (
        dict(trusted_feedback_status)
        if trusted_feedback_status is not None
        else build_trusted_user_feedback_status(runs_root)
    )
    rule_updates = (
        dict(rule_update_status)
        if rule_update_status is not None
        else build_rule_update_status(runs_root)
    )
    manifest_path = (
        Path(regression_manifest_path).expanduser().resolve()
        if regression_manifest_path is not None
        else None
    )
    actions = [
        _dogfood_action(dogfood),
        _physical_action(physical, runs_dir=runs_root),
        _failure_capture_action(failures),
        _regression_action(
            regression,
            regression_manifest_path=manifest_path,
            failure_regression_status=failure_regressions,
        ),
        _trusted_user_action(trusted_feedback),
        _rules_action(failures, rule_updates),
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
            "dogfood_status": dogfood,
            "failure_report_count": len(failures),
            "failure_reports": failures,
            "failure_regression_status": failure_regressions,
            "physical_status": physical,
            "trusted_feedback_status": trusted_feedback,
            "rule_update_status": rule_updates,
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


def _dogfood_action(status: Mapping[str, Any]) -> dict[str, str]:
    if status.get("overall_status") == "passed":
        non_slipper_count = int(status.get("non_slipper_passed_count") or 0)
        required_count = int(status.get("required_non_slipper_count") or 3)
        return {
            "id": "run_beta_dogfood",
            "label": "Dogfood canonical object matrix",
            "status": "ready",
            "detail": (
                "Software dogfood evidence found: slipper software run plus "
                f"{non_slipper_count} / {required_count} non-slipper live-sliced runs. "
                "Physical print proof and trusted-user feedback remain separate gates."
            ),
            "command": "",
        }
    slipper_status = str(status.get("slipper_status") or "missing")
    non_slipper_count = int(status.get("non_slipper_passed_count") or 0)
    required_count = int(status.get("required_non_slipper_count") or 3)
    detail = (
        "Run the slipper proof plus at least three non-slipper objects through "
        "the current pipeline and record the outcomes."
    )
    if status.get("overall_status") == "incomplete":
        detail = (
            f"Software dogfood matrix incomplete: slipper={slipper_status}; "
            f"{non_slipper_count} / {required_count} non-slipper live-sliced runs found."
        )
    return {
        "id": "run_beta_dogfood",
        "label": "Dogfood canonical object matrix",
        "status": "action_required",
        "detail": detail,
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
    failure_regression_status: Mapping[str, Any],
) -> dict[str, str]:
    coverage_status = str(failure_regression_status.get("overall_status") or "")
    if coverage_status in {"missing_manifest", "missing_regressions", "invalid_manifest"}:
        failure_count = int(failure_regression_status.get("failure_report_count") or 0)
        covered_count = int(failure_regression_status.get("covered_failure_count") or 0)
        missing = ", ".join(
            _list_of_strings(
                failure_regression_status.get("missing_regression_source_run_ids")
            )
        )
        detail = f"{covered_count} / {failure_count} captured failures have regression cases."
        if missing:
            detail += f" Missing: {missing}."
        manifest_label = (
            _quote(str(regression_manifest_path))
            if regression_manifest_path is not None
            else '"regressions/beta_regressions.json"'
        )
        return {
            "id": "run_regressions",
            "label": "Replay captured regressions",
            "status": "action_required",
            "detail": detail,
            "command": f"printpipe run-regressions {manifest_label} --strict",
        }

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


def _trusted_user_action(status: Mapping[str, Any]) -> dict[str, str]:
    current = int(status.get("unique_trusted_user_count") or 0)
    required = int(status.get("required_trusted_user_count") or 3)
    if status.get("overall_status") == "passed":
        return {
            "id": "trusted_user_beta",
            "label": "Trusted-user beta",
            "status": "ready",
            "detail": f"{current} / {required} trusted users completed feedback.",
            "command": "",
        }
    return {
        "id": "trusted_user_beta",
        "label": "Trusted-user beta",
        "status": "action_required",
        "detail": (
            f"{current} / {required} trusted users completed feedback; collect "
            "successful and failed run packets before calling beta complete."
        ),
        "command": (
            'printpipe record-beta-feedback "<run-root>" --tester "<name>" '
            '--input-type existing_stl --material "<material>" '
            '--printer "Bambu Lab P2S" --outcome "<passed|failed|partial>" '
            '--summary "<what happened>" --would-print "<yes|no|unknown>" '
            '--recommendation "<recommendation>"'
        ),
    }


def _rules_action(
    failure_reports: list[dict[str, Any]],
    rule_update_status: Mapping[str, Any],
) -> dict[str, str]:
    if rule_update_status.get("overall_status") == "passed":
        return {
            "id": "update_rules",
            "label": "Update material/orientation/repair rules",
            "status": "ready",
            "detail": "Material, orientation, and repair rule updates have verified packets.",
            "command": "printpipe rule-update-status --runs-dir runs --strict",
        }
    missing_types = ", ".join(_list_of_strings(rule_update_status.get("missing_rule_types")))
    command = (
        'printpipe record-rule-update "<run-root>" --rule-type material '
        '--status verified --summary "<what changed>" --source "<failure or dogfood>" '
        '--changed-file "<path>" --test "<pytest or smoke command>"'
    )
    if failure_reports:
        detail = (
            "Review captured failures and patch material/orientation/repair "
            "rules when the same cause repeats."
        )
        if missing_types:
            detail += f" Missing verified rule types: {missing_types}."
        return {
            "id": "update_rules",
            "label": "Update material/orientation/repair rules",
            "status": "action_required",
            "detail": detail,
            "command": command,
        }
    if rule_update_status.get("overall_status") == "incomplete":
        detail = "Rule-update packets exist but are not complete."
        if missing_types:
            detail += f" Missing verified rule types: {missing_types}."
        return {
            "id": "update_rules",
            "label": "Update material/orientation/repair rules",
            "status": "action_required",
            "detail": detail,
            "command": command,
        }
    return {
        "id": "update_rules",
        "label": "Update material/orientation/repair rules",
        "status": "waiting_for_evidence",
        "detail": (
            "No captured beta failures exist yet, so rule changes would be guesses."
        ),
        "command": command,
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
    for report_path in sorted(runs_dir.glob("**/90_beta/failure_report.json")):
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


def _build_dogfood_software_status(runs_dir: Path) -> dict[str, Any]:
    required_non_slipper_count = 3
    base = {
        "schema_version": 1,
        "required_non_slipper_count": required_non_slipper_count,
        "non_slipper_passed_count": 0,
        "non_slipper_runs": [],
        "slipper_status": "missing",
        "slipper_run": None,
    }
    if not runs_dir.exists():
        return {"overall_status": "missing", **base}

    candidates: list[dict[str, Any]] = []
    slipper_run: dict[str, Any] | None = None
    non_slipper_by_category: dict[str, dict[str, Any]] = {}
    for report_path in sorted(runs_dir.glob("**/80_reports/run_report.json")):
        candidate = _dogfood_candidate(report_path)
        if candidate is None:
            continue
        candidates.append(candidate)
        if candidate["category"] == "slipper":
            if candidate["passed"] and slipper_run is None:
                slipper_run = candidate
            continue
        if candidate["passed"]:
            non_slipper_by_category.setdefault(candidate["category"], candidate)

    non_slipper_runs = [
        _dogfood_summary(candidate)
        for candidate in sorted(
            non_slipper_by_category.values(),
            key=lambda value: str(value["category"]),
        )
    ]
    slipper_status = "passed" if slipper_run is not None else "missing"
    if slipper_run is None and any(
        candidate["category"] == "slipper" for candidate in candidates
    ):
        slipper_status = "incomplete"
    non_slipper_passed_count = len(non_slipper_runs)
    if slipper_status == "passed" and non_slipper_passed_count >= required_non_slipper_count:
        overall_status = "passed"
    elif candidates:
        overall_status = "incomplete"
    else:
        overall_status = "missing"
    return {
        "overall_status": overall_status,
        **base,
        "non_slipper_passed_count": non_slipper_passed_count,
        "non_slipper_runs": non_slipper_runs,
        "slipper_status": slipper_status,
        "slipper_run": _dogfood_summary(slipper_run) if slipper_run else None,
    }


def _dogfood_candidate(report_path: Path) -> dict[str, Any] | None:
    report = _read_json(report_path)
    if not report:
        return None
    run_root = report_path.parents[1]
    manifest = _read_json(run_root / "manifest.json")
    run_id = str(report.get("run_id") or manifest.get("run_id") or run_root.name)
    source_path = _manifest_source_path(manifest)
    category = _dogfood_category(run_id=run_id, source_path=source_path)
    if category is None:
        return None
    warnings = _list(report.get("warnings"))
    stages = [_dict(item) for item in _list(report.get("stages"))]
    stage_status = {
        str(item.get("stage") or ""): str(item.get("status") or "")
        for item in stages
    }
    failed_stage_count = sum(1 for status in stage_status.values() if status == "failed")
    bundle_ok = _stage_succeeded(stage_status, "bundle") and _stage_succeeded(
        stage_status,
        "bundle_validation",
    )
    slice_passed = _slice_result_passed(run_root)
    if category == "slipper":
        passed = (
            not warnings
            and failed_stage_count == 0
            and bundle_ok
            and _slipper_flex_coupon_recorded(run_root, stage_status)
        )
    else:
        passed = (
            not warnings
            and failed_stage_count == 0
            and bundle_ok
            and slice_passed
        )
    return {
        "run_id": run_id,
        "run_root": str(run_root),
        "source_path": source_path,
        "category": category,
        "passed": passed,
        "warning_count": len(warnings),
        "failed_stage_count": failed_stage_count,
        "slice_passed": slice_passed,
        "bundle_validated": bundle_ok,
    }


def _dogfood_category(*, run_id: str, source_path: str) -> str | None:
    text = f"{run_id} {source_path}".lower()
    if "slipper" in text:
        return "slipper"
    if "figurine" in text:
        return "figurine"
    if "cup" in text or "vase" in text:
        return "cup_vase"
    if "flat" in text or "bracket" in text:
        return "flat_bracket"
    return None


def _dogfood_summary(candidate: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if candidate is None:
        return None
    return {
        "run_id": str(candidate.get("run_id") or ""),
        "run_root": str(candidate.get("run_root") or ""),
        "source_path": str(candidate.get("source_path") or ""),
        "category": str(candidate.get("category") or ""),
        "slice_passed": bool(candidate.get("slice_passed")),
        "bundle_validated": bool(candidate.get("bundle_validated")),
    }


def _manifest_source_path(manifest: Mapping[str, Any]) -> str:
    input_data = _dict(manifest.get("input"))
    return str(input_data.get("source_path") or input_data.get("stored_path") or "")


def _stage_succeeded(stage_status: Mapping[str, str], stage_name: str) -> bool:
    return stage_status.get(stage_name) == "succeeded"


def _slipper_flex_coupon_recorded(
    run_root: Path,
    stage_status: Mapping[str, str],
) -> bool:
    if stage_status.get("validation.flex_coupon") == "succeeded":
        return True
    return any(run_root.glob("40_geometry/flex_coupon*.stl"))


def _slice_result_passed(run_root: Path) -> bool:
    payload = _read_json(run_root / "70_slice" / "slice_result.json")
    if not payload:
        return False
    return_code = payload.get("return_code")
    return (
        isinstance(return_code, int)
        and return_code == 0
        and not _list(payload.get("warnings"))
        and not _list(payload.get("errors"))
    )


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _list_of_strings(value: Any) -> list[str]:
    return [str(item) for item in _list(value)]


__all__ = [
    "BETA_PLAN_PROOF_BOUNDARY",
    "build_beta_action_plan",
    "render_beta_action_plan",
]
