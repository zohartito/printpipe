"""Combined beta and release readiness gates."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from printpipe.beta.feedback import build_trusted_user_feedback_status
from printpipe.beta.physical_status import build_physical_validation_status
from printpipe.beta.regression import (
    build_failure_regression_status,
    run_regression_manifest,
)
from printpipe.beta.rule_updates import build_rule_update_status
from printpipe.env.doctor import build_environment_report

READY = "ready"
ACTION_REQUIRED = "action_required"
NOT_APPLICABLE = "not_applicable"


def build_beta_readiness_report(
    runs_dir: str | Path,
    *,
    physical_status: Mapping[str, Any] | None = None,
    trusted_feedback_status: Mapping[str, Any] | None = None,
    rule_update_status: Mapping[str, Any] | None = None,
    failure_regression_status: Mapping[str, Any] | None = None,
    environment_report: Mapping[str, Any] | None = None,
    regression_status: Mapping[str, Any] | None = None,
    regression_manifest_path: str | Path | None = None,
) -> dict[str, Any]:
    """Return a single JSON-friendly readiness report for beta/release gates."""

    physical = (
        dict(physical_status)
        if physical_status is not None
        else build_physical_validation_status(runs_dir)
    )
    environment = (
        dict(environment_report)
        if environment_report is not None
        else build_environment_report()
    )
    regression = _regression_status(
        regression_status=regression_status,
        regression_manifest_path=regression_manifest_path,
    )
    failure_regressions = (
        dict(failure_regression_status)
        if failure_regression_status is not None
        else build_failure_regression_status(
            runs_dir,
            regression_manifest_path=regression_manifest_path,
        )
    )
    trusted_feedback = (
        dict(trusted_feedback_status)
        if trusted_feedback_status is not None
        else build_trusted_user_feedback_status(runs_dir)
    )
    rule_updates = (
        dict(rule_update_status)
        if rule_update_status is not None
        else build_rule_update_status(runs_dir)
    )
    gates = [
        _physical_gate(physical),
        _trusted_feedback_gate(trusted_feedback),
        _rule_updates_gate(rule_updates),
        _failure_regressions_gate(failure_regressions),
        _regression_gate(regression, regression_manifest_path=regression_manifest_path),
        _dependency_gate(environment),
        _meshgen_gate(environment),
        _filesystem_gate(environment),
        _bambu_studio_gate(environment),
        _bambu_profiles_gate(environment),
        _signing_gate(environment),
    ]
    actionable = [gate for gate in gates if gate["status"] == ACTION_REQUIRED]
    return {
        "schema_version": 1,
        "overall_status": ACTION_REQUIRED if actionable else READY,
        "action_required_count": len(actionable),
        "gates": gates,
        "physical_status": physical,
        "trusted_feedback_status": trusted_feedback,
        "rule_update_status": rule_updates,
        "failure_regression_status": failure_regressions,
        "regression_status": regression,
        "environment_summary": {
            "platform": _dict(environment.get("platform")),
            "summary": _dict(environment.get("summary")),
            "meshgen": _dict(environment.get("meshgen")),
        },
    }


def render_beta_readiness_report(report: Mapping[str, Any]) -> str:
    """Render a concise human-readable readiness report."""

    lines = [
        "PrintPipe Readiness",
        f"overall: {report.get('overall_status', 'unknown')}",
        f"action required: {report.get('action_required_count', 0)}",
        "Gates:",
    ]
    for gate in _list(report.get("gates")):
        gate_dict = _dict(gate)
        label = gate_dict.get("label") or gate_dict.get("id") or "Unknown gate"
        status = gate_dict.get("status", "unknown")
        detail = gate_dict.get("detail", "")
        action = gate_dict.get("action", "")
        line = f"- {status}: {label}"
        if detail:
            line += f" - {detail}"
        if action:
            line += f" Action: {action}"
        lines.append(line)
    return "\n".join(lines) + "\n"


def _physical_gate(physical_status: Mapping[str, Any]) -> dict[str, Any]:
    if physical_status.get("overall_status") == "passed":
        return _gate(
            "physical_validation",
            "Physical validation",
            READY,
            "PLA, PETG, and TPU physical evidence packets have passed.",
            "No action needed.",
        )
    families = [
        family.upper()
        for family, status in sorted(_dict(physical_status.get("family_status")).items())
        if _dict(status).get("status") != "passed"
    ]
    family_label = ", ".join(families) if families else "PLA, PETG, and TPU"
    return _gate(
        "physical_validation",
        "Physical validation",
        ACTION_REQUIRED,
        f"Missing passed physical evidence for: {family_label}.",
        "Print and record passed PLA, PETG, and TPU coupon or small-object evidence.",
    )


def _trusted_feedback_gate(status: Mapping[str, Any]) -> dict[str, Any]:
    current = int(status.get("unique_trusted_user_count") or 0)
    required = int(status.get("required_trusted_user_count") or 3)
    if status.get("overall_status") == "passed":
        return _gate(
            "trusted_user_beta",
            "Trusted-user beta",
            READY,
            f"{current} / {required} trusted users completed feedback.",
            "No action needed.",
        )
    return _gate(
        "trusted_user_beta",
        "Trusted-user beta",
        ACTION_REQUIRED,
        f"{current} / {required} trusted users completed feedback.",
        "Give the app to 3 trusted users and record each packet with record-beta-feedback.",
    )


def _rule_updates_gate(status: Mapping[str, Any]) -> dict[str, Any]:
    overall = str(status.get("overall_status") or "missing")
    if overall == "passed":
        return _gate(
            "rule_updates",
            "Rule updates",
            READY,
            "Material, orientation, and repair rule updates have verified packets.",
            "No action needed.",
        )
    if overall == "missing":
        return _gate(
            "rule_updates",
            "Rule updates",
            NOT_APPLICABLE,
            "No material/orientation/repair rule-update packets recorded.",
            "Record rule updates after captured beta failures or dogfood fixes.",
        )
    missing = [
        str(item)
        for item in _list(status.get("missing_rule_types"))
        if str(item)
    ]
    missing_label = ", ".join(missing) if missing else "unverified updates"
    return _gate(
        "rule_updates",
        "Rule updates",
        ACTION_REQUIRED,
        f"Missing verified rule-update packets for: {missing_label}.",
        "Record verified material/orientation/repair updates with record-rule-update.",
    )


def _failure_regressions_gate(status: Mapping[str, Any]) -> dict[str, Any]:
    overall = str(status.get("overall_status") or "no_failures")
    failure_count = int(status.get("failure_report_count") or 0)
    covered_count = int(status.get("covered_failure_count") or 0)
    if overall == "no_failures":
        return _gate(
            "failure_regressions",
            "Failure regressions",
            NOT_APPLICABLE,
            "No captured beta failure packets are recorded.",
            "Capture failures with record-beta-failure when they happen.",
        )
    if overall == "passed":
        return _gate(
            "failure_regressions",
            "Failure regressions",
            READY,
            f"{covered_count} / {failure_count} captured failures have regression cases.",
            "Run printpipe run-regressions before release claims.",
        )
    missing = [
        str(item)
        for item in _list(status.get("missing_regression_source_run_ids"))
        if str(item)
    ]
    detail = f"{covered_count} / {failure_count} captured failures have regression cases."
    if missing:
        detail += " Missing: " + ", ".join(missing) + "."
    return _gate(
        "failure_regressions",
        "Failure regressions",
        ACTION_REQUIRED,
        detail,
        "Append regression cases for every captured failure with record-beta-failure.",
    )


def _meshgen_gate(environment: Mapping[str, Any]) -> dict[str, Any]:
    meshgen = _dict(environment.get("meshgen"))
    if not meshgen:
        return _gate(
            "media_meshgen",
            "Media meshgen provider",
            NOT_APPLICABLE,
            "No media meshgen provider readiness report is available.",
            "Run printpipe doctor to inspect local meshgen provider configuration.",
        )
    if meshgen.get("overall_status") == "ready":
        provider_count = int(meshgen.get("live_media_provider_count") or 0)
        return _gate(
            "media_meshgen",
            "Media meshgen provider",
            READY,
            f"{provider_count} live image/GIF/video meshgen provider(s) configured.",
            "No action needed.",
        )
    return _gate(
        "media_meshgen",
        "Media meshgen provider",
        ACTION_REQUIRED,
        str(meshgen.get("message") or "No live media meshgen provider is configured."),
        str(meshgen.get("action") or "Configure a live image/GIF/video meshgen provider."),
    )


def _regression_status(
    *,
    regression_status: Mapping[str, Any] | None,
    regression_manifest_path: str | Path | None,
) -> dict[str, Any]:
    if regression_status is not None:
        return dict(regression_status)
    if regression_manifest_path is not None:
        return run_regression_manifest(regression_manifest_path)
    return {"overall_status": "not_configured"}


def _regression_gate(
    regression_status: Mapping[str, Any],
    *,
    regression_manifest_path: str | Path | None,
) -> dict[str, Any]:
    overall_status = str(regression_status.get("overall_status") or "not_configured")
    case_count = int(regression_status.get("case_count") or 0)
    if overall_status == "passed":
        return _gate(
            "beta_regressions",
            "Beta regressions",
            READY,
            f"{case_count} captured regression case(s) matched expected outcomes.",
            "No action needed.",
        )
    if overall_status == "failed":
        failed_count = int(regression_status.get("failed_count") or 0)
        manifest_label = _optional_path_label(regression_manifest_path)
        return _gate(
            "beta_regressions",
            "Beta regressions",
            ACTION_REQUIRED,
            f"{failed_count} regression case(s) drifted from expected outcomes.",
            f"Run printpipe run-regressions {manifest_label} --strict and fix the drift.",
        )
    return _gate(
        "beta_regressions",
        "Beta regressions",
        NOT_APPLICABLE,
        "No beta regression manifest configured.",
        "Capture beta failures with record-beta-failure or pass --regression-manifest.",
    )


def _dependency_gate(environment_report: Mapping[str, Any]) -> dict[str, Any]:
    dependencies = [_dict(item) for item in _list(environment_report.get("dependencies"))]
    blocking = [
        str(item.get("label") or item.get("id") or "dependency")
        for item in dependencies
        if str(item.get("status", "")) in {"missing", "unsupported"}
    ]
    if not blocking:
        return _gate(
            "dependencies",
            "Dependencies",
            READY,
            "Required dependencies are available.",
            "No action needed.",
        )
    return _gate(
        "dependencies",
        "Dependencies",
        ACTION_REQUIRED,
        "Missing or unsupported dependencies: " + ", ".join(blocking) + ".",
        "Install or upgrade the required dependencies reported by doctor.",
    )


def _filesystem_gate(environment_report: Mapping[str, Any]) -> dict[str, Any]:
    checks = [_dict(item) for item in _list(_dict(environment_report.get("filesystem")).get("checks"))]
    warnings = [
        str(item.get("path") or item.get("label") or "path")
        for item in checks
        if str(item.get("status")) != "ok"
    ]
    if not warnings:
        return _gate(
            "filesystem",
            "Filesystem access",
            READY,
            "Workspace and configured artifact paths are readable.",
            "No action needed.",
        )
    return _gate(
        "filesystem",
        "Filesystem access",
        ACTION_REQUIRED,
        "Unreadable or missing paths: " + ", ".join(warnings) + ".",
        "Grant filesystem permission or move runs/artifacts to readable paths.",
    )


def _bambu_studio_gate(environment_report: Mapping[str, Any]) -> dict[str, Any]:
    installed_count = int(_dict(environment_report.get("bambu_studio")).get("installed_count") or 0)
    if installed_count > 0:
        return _gate(
            "bambu_studio",
            "Bambu Studio",
            READY,
            f"{installed_count} installed Bambu Studio candidate(s) found.",
            "No action needed.",
        )
    return _gate(
        "bambu_studio",
        "Bambu Studio",
        ACTION_REQUIRED,
        "No installed Bambu Studio candidate was found.",
        "Install Bambu Studio or configure the executable path before live slicing.",
    )


def _bambu_profiles_gate(environment_report: Mapping[str, Any]) -> dict[str, Any]:
    candidate_count = int(_dict(environment_report.get("bambu_profiles")).get("candidate_count") or 0)
    if candidate_count > 0:
        return _gate(
            "bambu_profiles",
            "Bambu profile folders",
            READY,
            f"{candidate_count} Bambu profile user folder(s) found.",
            "No action needed.",
        )
    return _gate(
        "bambu_profiles",
        "Bambu profile folders",
        ACTION_REQUIRED,
        "No Bambu profile user folders were found.",
        "Open Bambu Studio once or configure the profile directory.",
    )


def _signing_gate(environment_report: Mapping[str, Any]) -> dict[str, Any]:
    platform = str(_dict(environment_report.get("platform")).get("normalized") or "")
    signing = _dict(_dict(environment_report.get("system")).get("signing"))
    if not signing:
        return _gate(
            "signing",
            "Release signing",
            NOT_APPLICABLE,
            f"No signing gate is defined for platform {platform or 'unknown'}.",
            "No action needed.",
        )
    if signing.get("status") == "ready":
        return _gate(
            "signing",
            "Release signing",
            READY,
            "Release signing tools and identities are ready.",
            "No action needed.",
        )
    missing = [str(item) for item in _list(signing.get("missing_tools"))]
    missing.extend(str(item) for item in _list(signing.get("missing_identities")))
    detail = (
        "Missing signing requirements: " + ", ".join(missing) + "."
        if missing
        else f"Signing status is {signing.get('status', 'not ready')}."
    )
    return _gate(
        "signing",
        "Release signing",
        ACTION_REQUIRED,
        detail,
        "Install signing tools/certificates or keep release artifacts marked unsigned.",
    )


def _gate(
    gate_id: str,
    label: str,
    status: str,
    detail: str,
    action: str,
) -> dict[str, str]:
    return {
        "id": gate_id,
        "label": label,
        "status": status,
        "detail": detail,
        "action": action,
    }


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _optional_path_label(path: str | Path | None) -> str:
    if path is None:
        return "<manifest>"
    return str(Path(path).expanduser())


__all__ = ["build_beta_readiness_report", "render_beta_readiness_report"]
