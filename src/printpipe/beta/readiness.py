"""Combined beta and release readiness gates."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from printpipe.beta.physical_status import build_physical_validation_status
from printpipe.env.doctor import build_environment_report

READY = "ready"
ACTION_REQUIRED = "action_required"
NOT_APPLICABLE = "not_applicable"


def build_beta_readiness_report(
    runs_dir: str | Path,
    *,
    physical_status: Mapping[str, Any] | None = None,
    environment_report: Mapping[str, Any] | None = None,
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
    gates = [
        _physical_gate(physical),
        _dependency_gate(environment),
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
        "environment_summary": {
            "platform": _dict(environment.get("platform")),
            "summary": _dict(environment.get("summary")),
        },
    }


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


__all__ = ["build_beta_readiness_report"]
