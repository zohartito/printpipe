"""Developer ID signing and notarization helpers for macOS artifacts."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable

CommandRunner = Callable[[list[str]], subprocess.CompletedProcess[str]]


def sign_macos_path(
    path: str | Path,
    *,
    identity: str,
    codesign_path: str | None = None,
    runner: CommandRunner | None = None,
) -> dict[str, Any]:
    """Developer ID sign a macOS bundle or artifact and verify the signature."""

    target = Path(path).expanduser()
    codesign = codesign_path or shutil.which("codesign")
    if codesign is None:
        raise RuntimeError("codesign is required for Developer ID signing")
    run = _run_command if runner is None else runner
    sign_command = [
        codesign,
        "--force",
        "--deep",
        "--options",
        "runtime",
        "--timestamp",
        "--sign",
        identity,
        str(target),
    ]
    _run_checked(run, sign_command, "codesign failed")
    verify_command = [
        codesign,
        "--verify",
        "--deep",
        "--strict",
        str(target),
    ]
    _run_checked(run, verify_command, "codesign verification failed")
    return {
        "status": "ok",
        "path": str(target),
        "identity": identity,
        "verified": True,
        "sign_command": sign_command,
        "verify_command": verify_command,
    }


def notarize_macos_artifact(
    artifact_path: str | Path,
    *,
    keychain_profile: str,
    xcrun_path: str | None = None,
    runner: CommandRunner | None = None,
) -> dict[str, Any]:
    """Submit a signed macOS artifact to Apple notarytool and staple it."""

    target = Path(artifact_path).expanduser()
    xcrun = xcrun_path or shutil.which("xcrun")
    if xcrun is None:
        raise RuntimeError("xcrun/notarytool is required for macOS notarization")
    run = _run_command if runner is None else runner
    submit_command = [
        xcrun,
        "notarytool",
        "submit",
        str(target),
        "--keychain-profile",
        keychain_profile,
        "--wait",
        "--output-format",
        "json",
    ]
    submission = _run_checked(run, submit_command, "notarytool submit failed")
    payload = _parse_notarytool_json(submission.stdout)
    status = str(payload.get("status") or "")
    if status.lower() != "accepted":
        raise RuntimeError(f"notarization was not accepted: {status or 'unknown'}")
    staple_command = [xcrun, "stapler", "staple", str(target)]
    _run_checked(run, staple_command, "notary stapler failed")
    return {
        "status": "ok",
        "artifact_path": str(target),
        "submission_id": str(payload.get("id") or ""),
        "notary_status": status,
        "stapled": True,
        "submit_command": submit_command,
        "staple_command": staple_command,
    }


def _run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, capture_output=True, check=False)


def _run_checked(
    runner: CommandRunner,
    command: list[str],
    failure_label: str,
) -> subprocess.CompletedProcess[str]:
    result = runner(command)
    if result.returncode != 0:
        message = (result.stderr or result.stdout or failure_label).strip()
        raise RuntimeError(message)
    return result


def _parse_notarytool_json(stdout: str) -> dict[str, Any]:
    try:
        payload = json.loads(stdout or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError("notarytool did not return JSON") from exc
    return payload if isinstance(payload, dict) else {}


__all__ = ["notarize_macos_artifact", "sign_macos_path"]
