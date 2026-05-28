"""Combined release-folder and readiness status report."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from printpipe.beta.readiness import (
    ACTION_REQUIRED,
    READY,
    build_beta_readiness_report,
)
from printpipe.packaging.release import verify_release_bundle


def build_release_status_report(
    *,
    release_dir: str | Path,
    runs_dir: str | Path,
    regression_manifest_path: str | Path | None = None,
    release_verification: Mapping[str, Any] | None = None,
    readiness_report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return one JSON-friendly report for release integrity and ship gates."""

    release_path = Path(release_dir).expanduser()
    runs_path = Path(runs_dir).expanduser()
    verification = (
        dict(release_verification)
        if release_verification is not None
        else verify_release_bundle(release_path)
    )
    readiness = (
        dict(readiness_report)
        if readiness_report is not None
        else build_beta_readiness_report(
            runs_path,
            regression_manifest_path=regression_manifest_path,
        )
    )
    release_artifacts = _release_artifacts(release_path, verification)
    gates = [_release_bundle_gate(release_path, verification)]
    gates.extend(_distribution_gates(release_artifacts, verification))
    gates.extend(_dict(gate) for gate in _list(readiness.get("gates")))
    actionable = [gate for gate in gates if gate.get("status") == ACTION_REQUIRED]
    return {
        "schema_version": 1,
        "overall_status": ACTION_REQUIRED if actionable else READY,
        "action_required_count": len(actionable),
        "release_dir": str(release_path),
        "runs_dir": str(runs_path),
        "gates": gates,
        "next_actions": _next_actions(actionable),
        "release_artifacts": release_artifacts,
        "release_verification": verification,
        "readiness": readiness,
    }


def render_release_status_report(report: Mapping[str, Any]) -> str:
    """Render a concise human-readable release status report."""

    lines = [
        "PrintPipe Release Status",
        f"overall: {report.get('overall_status', 'unknown')}",
        f"action required: {report.get('action_required_count', 0)}",
        f"release dir: {report.get('release_dir', '')}",
        f"runs dir: {report.get('runs_dir', '')}",
        "Gates:",
    ]
    for gate in _list(report.get("gates")):
        gate_dict = _dict(gate)
        label = gate_dict.get("label") or gate_dict.get("id") or "Unknown gate"
        status = gate_dict.get("status", "unknown")
        detail = gate_dict.get("detail", "")
        line = f"- {status}: {label}"
        if detail:
            line += f" - {detail}"
        lines.append(line)
    actions = [str(action) for action in _list(report.get("next_actions")) if str(action)]
    if actions:
        lines.append("Next actions:")
        lines.extend(f"- {action}" for action in actions)
    return "\n".join(lines) + "\n"


def _release_bundle_gate(
    release_dir: Path,
    verification: Mapping[str, Any],
) -> dict[str, str]:
    if verification.get("status") == "ok":
        artifact_count = int(verification.get("artifact_count") or 0)
        return _gate(
            "release_bundle",
            "Release bundle",
            READY,
            f"Release manifest and {artifact_count} artifact(s) verify.",
            "No action needed.",
        )
    failures = [_dict(failure) for failure in _list(verification.get("failures"))]
    failure_ids = [
        str(failure.get("id"))
        for failure in failures[:3]
        if failure.get("id")
    ]
    detail = f"{len(failures)} release verification check(s) failed"
    if failure_ids:
        detail += ": " + ", ".join(failure_ids)
    detail += "."
    return _gate(
        "release_bundle",
        "Release bundle",
        ACTION_REQUIRED,
        detail,
        f"Run printpipe verify-release {release_dir} --json and rebuild or repair the release bundle.",
    )


def _distribution_gates(
    artifacts: list[dict[str, Any]],
    verification: Mapping[str, Any],
) -> list[dict[str, str]]:
    if not artifacts:
        return []
    return [
        _macos_distribution_gate(artifacts, verification),
        _windows_distribution_gate(artifacts, verification),
    ]


def _macos_distribution_gate(
    artifacts: list[dict[str, Any]],
    verification: Mapping[str, Any],
) -> dict[str, str]:
    macos_artifacts = [
        artifact
        for artifact in artifacts
        if str(artifact.get("kind", "")).startswith("macos_")
    ]
    if not macos_artifacts:
        return _gate(
            "macos_distribution",
            "macOS distribution",
            ACTION_REQUIRED,
            "No macOS release artifact is recorded in the manifest.",
            "Build a macOS release artifact before a strict release handoff.",
        )
    has_verified_shape = any(
        artifact.get("kind") == "macos_dmg"
        and artifact.get("signed") is True
        and artifact.get("notarized") is True
        for artifact in macos_artifacts
    )
    if has_verified_shape and verification.get("status") == "ok":
        return _gate(
            "macos_distribution",
            "macOS distribution",
            READY,
            "A Developer ID signed and notarized macOS DMG is recorded.",
            "No action needed.",
        )
    if has_verified_shape:
        return _gate(
            "macos_distribution",
            "macOS distribution",
            ACTION_REQUIRED,
            "macOS Developer ID notarization is recorded in the manifest but not verified.",
            "Run printpipe verify-release and rebuild or repair the macOS release artifact.",
        )
    return _gate(
        "macos_distribution",
        "macOS distribution",
        ACTION_REQUIRED,
        "macOS release artifact is not Developer ID signed and notarized.",
        "Install Developer ID identities, configure notarytool, and rebuild the release DMG.",
    )


def _windows_distribution_gate(
    artifacts: list[dict[str, Any]],
    verification: Mapping[str, Any],
) -> dict[str, str]:
    has_verified_shape = any(
        artifact.get("kind") == "windows_installer"
        and artifact.get("signed") is True
        for artifact in artifacts
    )
    if has_verified_shape and verification.get("status") == "ok":
        return _gate(
            "windows_distribution",
            "Windows distribution",
            READY,
            "A signed Windows installer artifact is recorded.",
            "No action needed.",
        )
    if has_verified_shape:
        return _gate(
            "windows_distribution",
            "Windows distribution",
            ACTION_REQUIRED,
            "A signed Windows installer is recorded in the manifest but not verified.",
            "Run printpipe verify-release and rebuild or repair the Windows installer.",
        )
    return _gate(
        "windows_distribution",
        "Windows distribution",
        ACTION_REQUIRED,
        "No signed Windows installer artifact is recorded in the manifest.",
        "Build and include a signed PrintPipeSetup.exe before a strict release handoff.",
    )


def _release_artifacts(
    release_dir: Path,
    verification: Mapping[str, Any],
) -> list[dict[str, Any]]:
    artifacts = [_dict(artifact) for artifact in _list(verification.get("artifacts"))]
    if artifacts:
        return artifacts
    manifest_path = release_dir / "release_manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return [_dict(artifact) for artifact in _list(_dict(manifest).get("artifacts"))]


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


def _next_actions(gates: list[Mapping[str, Any]]) -> list[str]:
    actions: list[str] = []
    seen: set[str] = set()
    for gate in gates:
        action = str(gate.get("action") or "").strip()
        if not action or action == "No action needed." or action in seen:
            continue
        actions.append(action)
        seen.add(action)
    return actions


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


__all__ = ["build_release_status_report", "render_release_status_report"]
