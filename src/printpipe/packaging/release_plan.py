"""Action plan helpers for final release distribution gates."""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any, Mapping

from printpipe.beta.readiness import ACTION_REQUIRED, READY
from printpipe.packaging.release_status import build_release_status_report

RELEASE_PLAN_PROOF_BOUNDARY = (
    "A release plan is not signed distribution evidence. Only verified release "
    "manifest artifacts with Developer ID notarization or Authenticode signing "
    "close the final distribution gates."
)


def build_release_distribution_plan(
    *,
    release_dir: str | Path,
    runs_dir: str | Path,
    regression_manifest_path: str | Path | None = None,
    release_status_report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Turn release distribution gate failures into concrete commands."""

    release_path = Path(release_dir).expanduser()
    runs_path = Path(runs_dir).expanduser()
    status = (
        dict(release_status_report)
        if release_status_report is not None
        else build_release_status_report(
            release_dir=release_path,
            runs_dir=runs_path,
            regression_manifest_path=regression_manifest_path,
        )
    )
    gates = {_dict(gate).get("id"): _dict(gate) for gate in _list(status.get("gates"))}
    actions = _release_actions(
        gates=gates,
        release_dir=release_path,
        runs_dir=runs_path,
        regression_manifest_path=regression_manifest_path,
    )
    return {
        "schema_version": 1,
        "release_dir": str(release_path),
        "runs_dir": str(runs_path),
        "overall_status": ACTION_REQUIRED if actions else READY,
        "action_count": len(actions),
        "proof_boundary": RELEASE_PLAN_PROOF_BOUNDARY,
        "actions": actions,
        "release_status": status,
    }


def render_release_distribution_plan(plan: Mapping[str, Any]) -> str:
    """Render a human-readable release distribution action plan."""

    lines = [
        "PrintPipe Release Distribution Plan",
        f"overall: {plan.get('overall_status', 'unknown')}",
        f"action required: {plan.get('action_count', 0)}",
        f"release dir: {plan.get('release_dir', '')}",
        f"runs dir: {plan.get('runs_dir', '')}",
        "",
        str(plan.get("proof_boundary", RELEASE_PLAN_PROOF_BOUNDARY)),
        "",
    ]
    actions = _list(plan.get("actions"))
    if not actions:
        lines.append("No release distribution actions required.")
        return "\n".join(lines) + "\n"
    lines.append("Actions:")
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
        followup = str(item.get("followup_command") or "")
        if followup:
            lines.append(f"  follow-up: {followup}")
    return "\n".join(lines) + "\n"


def _release_actions(
    *,
    gates: Mapping[Any, Mapping[str, Any]],
    release_dir: Path,
    runs_dir: Path,
    regression_manifest_path: str | Path | None,
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    release_bundle_gate = _dict(gates.get("release_bundle"))
    if release_bundle_gate.get("status") == ACTION_REQUIRED:
        actions.append(_release_bundle_action(release_dir=release_dir))
    macos_gate = _dict(gates.get("macos_distribution"))
    if macos_gate.get("status") == ACTION_REQUIRED:
        actions.append(_macos_distribution_action(release_dir=release_dir))
    windows_gate = _dict(gates.get("windows_distribution"))
    if windows_gate.get("status") == ACTION_REQUIRED:
        actions.append(_windows_distribution_action(release_dir=release_dir))
    signing_gate = _dict(gates.get("signing"))
    if (
        signing_gate.get("status") == ACTION_REQUIRED
        and not any(action["id"] == "signing" for action in actions)
    ):
        actions.append(_signing_prerequisite_action(runs_dir=runs_dir))
    return actions


def _release_bundle_action(*, release_dir: Path) -> dict[str, Any]:
    return {
        "id": "release_bundle",
        "label": "Release bundle",
        "status": ACTION_REQUIRED,
        "detail": "Rebuild and verify the release handoff folder.",
        "command": (
            "printpipe build-release --output-dir "
            f"{_quote(str(release_dir))} --adhoc-sign --include-standalone --json"
        ),
        "followup_command": f"printpipe verify-release {_quote(str(release_dir))} --json",
        "required_inputs": ["release output directory"],
    }


def _macos_distribution_action(*, release_dir: Path) -> dict[str, Any]:
    return {
        "id": "macos_distribution",
        "label": "macOS distribution",
        "status": ACTION_REQUIRED,
        "detail": (
            "Install Developer ID Application credentials, configure a notarytool "
            "keychain profile, then rebuild the release with notarization enabled."
        ),
        "command": (
            "printpipe build-release --output-dir "
            f"{_quote(str(release_dir))} --developer-id-identity "
            '"<Developer ID Application: Name (TEAMID)>" --notary-profile '
            '"<notarytool-profile>" --include-standalone --json'
        ),
        "followup_command": f"printpipe release-status --release-dir {_quote(str(release_dir))} --strict",
        "required_inputs": [
            "Developer ID Application certificate",
            "Developer ID Installer certificate",
            "notarytool keychain profile",
            "Apple Developer account",
        ],
    }


def _windows_distribution_action(*, release_dir: Path) -> dict[str, Any]:
    installer_path = release_dir / "PrintPipeSetup.exe"
    standalone_path = release_dir / "PrintPipe-Windows-standalone.zip"
    return {
        "id": "windows_distribution",
        "label": "Windows distribution",
        "status": ACTION_REQUIRED,
        "detail": (
            "Build a native Windows installer from the standalone ZIP, sign it "
            "with Authenticode, then include it in the release manifest."
        ),
        "command": (
            "printpipe build-windows-installer --standalone-zip "
            f"{_quote(str(standalone_path))} --output {_quote(str(installer_path))} "
            '--certificate-subject "<Code Signing Certificate Subject>" --json'
        ),
        "followup_command": (
            "printpipe build-release --output-dir "
            f"{_quote(str(release_dir))} --windows-installer-exe "
            f"{_quote(str(installer_path))} --json"
        ),
        "required_inputs": [
            "Windows standalone ZIP",
            "signtool",
            "Inno Setup, WiX, or NSIS",
            "Code-signing certificate",
        ],
    }


def _signing_prerequisite_action(*, runs_dir: Path) -> dict[str, Any]:
    return {
        "id": "signing",
        "label": "Release signing prerequisites",
        "status": ACTION_REQUIRED,
        "detail": "Inspect local signing tools and certificate readiness before final release claims.",
        "command": "printpipe doctor --json",
        "followup_command": f"printpipe readiness --runs-dir {_quote(str(runs_dir))} --strict",
        "required_inputs": [
            "Developer ID Application identity",
            "Developer ID Installer identity",
            "Windows code-signing certificate",
        ],
    }


def _quote(value: str) -> str:
    return shlex.quote(value)


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


__all__ = [
    "RELEASE_PLAN_PROOF_BOUNDARY",
    "build_release_distribution_plan",
    "render_release_distribution_plan",
]
