"""Dependency preflight checks for local PrintPipe launch requirements."""

from __future__ import annotations

import importlib.util
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

DependencyStatus = str

MINIMUM_PYTHON_VERSION = (3, 11)
BAMBU_STUDIO_CLI_ENV = "PRINTPIPE_BAMBU_STUDIO_CLI"
BLENDER_ENV = "PRINTPIPE_BLENDER"

_OK_ACTION = "No action needed."


@dataclass(frozen=True)
class DependencyReport:
    """JSON-friendly status for one dependency or executable."""

    id: str
    label: str
    status: DependencyStatus
    action: str
    details: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "label": self.label,
            "status": self.status,
            "action": self.action,
            "details": dict(self.details),
        }


def check_dependency_preflight(
    *,
    python_version: Sequence[object] = sys.version_info,
    environ: Mapping[str, str] | None = None,
) -> list[dict[str, object]]:
    """Return JSON-friendly reports for launch-time dependency checks."""

    env = os.environ if environ is None else environ
    reports = (
        check_python_version(python_version),
        check_module_available(
            "trimesh",
            label="trimesh",
            purpose="mesh inspection and repair",
            install_hint="Install trimesh to enable mesh inspection and repair.",
        ),
        check_executable(
            id="bambu_studio_cli",
            label="Bambu Studio CLI",
            path=_path_from_env(env, BAMBU_STUDIO_CLI_ENV),
            purpose="slicing 3MF bundles",
            missing_action=f"Set {BAMBU_STUDIO_CLI_ENV} to the Bambu Studio executable.",
        ),
        check_executable(
            id="blender",
            label="Blender",
            path=_path_from_env(env, BLENDER_ENV),
            purpose="mesh conversion and repair workflows",
            missing_action=f"Set {BLENDER_ENV} to the Blender executable.",
        ),
        check_module_available(
            "paho.mqtt.client",
            label="paho-mqtt",
            purpose="future printer status monitoring",
            install_hint="Install paho-mqtt to enable future printer status monitoring.",
        ),
    )
    return [report.to_dict() for report in reports]


def check_python_version(
    version_info: Sequence[object] = sys.version_info,
    minimum: tuple[int, int] = MINIMUM_PYTHON_VERSION,
) -> DependencyReport:
    """Check whether the running Python version satisfies PrintPipe."""

    current = _format_version(version_info)
    minimum_label = ".".join(str(part) for part in minimum)
    version_tuple = tuple(int(part) for part in version_info[: len(minimum)])
    status: DependencyStatus = "ok" if version_tuple >= minimum else "unsupported"
    action = _OK_ACTION if status == "ok" else f"Install Python {minimum_label} or newer."

    return DependencyReport(
        id="python",
        label="Python",
        status=status,
        action=action,
        details={
            "minimum": minimum_label,
            "current": current,
        },
    )


def check_module_available(
    module_name: str,
    *,
    label: str,
    purpose: str,
    install_hint: str | None = None,
    optional: bool = True,
    id: str | None = None,
) -> DependencyReport:
    """Check module availability without importing the optional module."""

    try:
        found = importlib.util.find_spec(module_name) is not None
    except ModuleNotFoundError:
        found = False
    status: DependencyStatus
    if found:
        status = "ok"
    elif optional:
        status = "optional_missing"
    else:
        status = "missing"

    if found:
        action = _OK_ACTION
    elif install_hint is not None:
        action = install_hint
    else:
        action = f"Install {label}."

    return DependencyReport(
        id=id or _module_report_id(module_name),
        label=label,
        status=status,
        action=action,
        details={
            "purpose": purpose,
            "module": module_name,
        },
    )


def check_executable(
    *,
    id: str,
    label: str,
    path: str | os.PathLike[str] | None,
    purpose: str,
    missing_action: str,
    optional: bool = True,
) -> DependencyReport:
    """Check whether a configured executable path exists and is runnable."""

    normalized_path = _normalize_path(path)
    details = {
        "purpose": purpose,
        "path": str(normalized_path) if normalized_path is not None else None,
    }

    if normalized_path is None:
        return DependencyReport(
            id=id,
            label=label,
            status="optional_missing" if optional else "missing",
            action=missing_action,
            details=details,
        )

    if not normalized_path.exists():
        return DependencyReport(
            id=id,
            label=label,
            status="missing",
            action=f"{label} path does not exist: {normalized_path}. {missing_action}",
            details=details,
        )

    if not normalized_path.is_file() or not os.access(normalized_path, os.X_OK):
        return DependencyReport(
            id=id,
            label=label,
            status="missing",
            action=f"{label} path is not executable: {normalized_path}. {missing_action}",
            details=details,
        )

    return DependencyReport(
        id=id,
        label=label,
        status="ok",
        action=_OK_ACTION,
        details=details,
    )


def _format_version(version_info: Sequence[object]) -> str:
    major = int(version_info[0])
    minor = int(version_info[1])
    micro = int(version_info[2]) if len(version_info) > 2 else 0
    return f"{major}.{minor}.{micro}"


def _module_report_id(module_name: str) -> str:
    parts = module_name.split(".")
    if len(parts) >= 2 and parts[0] == "paho" and parts[1] == "mqtt":
        return "paho_mqtt"
    return parts[0].replace("-", "_")


def _normalize_path(path: str | os.PathLike[str] | None) -> Path | None:
    if path is None:
        return None
    text = os.fspath(path).strip()
    if not text:
        return None
    return Path(text).expanduser()


def _path_from_env(env: Mapping[str, str], key: str) -> Path | None:
    return _normalize_path(env.get(key))
