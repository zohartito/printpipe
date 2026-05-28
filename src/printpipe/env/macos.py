from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

JsonDict = dict[str, object]
ToolFinder = Callable[[str], str | None]
CommandRunner = Callable[[list[str]], subprocess.CompletedProcess[str]]

_APPLE_SILICON_MACHINES = frozenset({"arm64", "aarch64"})
_INTEL_MACHINES = frozenset({"x86_64", "amd64", "i386", "i686"})


@dataclass(frozen=True)
class MacOSArchitectureSummary:
    machine: str
    processor: str
    kind: str
    is_apple_silicon: bool
    is_intel: bool

    def as_dict(self) -> JsonDict:
        return {
            "machine": self.machine,
            "processor": self.processor,
            "kind": self.kind,
            "is_apple_silicon": self.is_apple_silicon,
            "is_intel": self.is_intel,
        }


@dataclass(frozen=True)
class MacOSAppSupportPaths:
    home: Path
    user_application_support: Path
    user_caches: Path
    user_logs: Path
    user_preferences: Path
    local_applications: Path
    system_application_support: Path

    def as_dict(self) -> dict[str, str]:
        return {
            "home": str(self.home),
            "user_application_support": str(self.user_application_support),
            "user_caches": str(self.user_caches),
            "user_logs": str(self.user_logs),
            "user_preferences": str(self.user_preferences),
            "local_applications": str(self.local_applications),
            "system_application_support": str(self.system_application_support),
        }


@dataclass(frozen=True)
class PythonRuntimeSummary:
    executable: Path
    version: str
    version_info: tuple[int, int, int, str, int]
    implementation: str
    prefix: Path
    base_prefix: Path
    is_virtualenv: bool

    def as_dict(self) -> JsonDict:
        return {
            "executable": str(self.executable),
            "version": self.version,
            "version_info": list(self.version_info),
            "implementation": self.implementation,
            "prefix": str(self.prefix),
            "base_prefix": str(self.base_prefix),
            "is_virtualenv": self.is_virtualenv,
        }


@dataclass(frozen=True)
class MacOSSigningReadiness:
    status: str
    tools: dict[str, str | None]
    developer_id_application_identities: tuple[str, ...]
    developer_id_installer_identities: tuple[str, ...]
    missing_tools: tuple[str, ...]
    missing_identities: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "tools": {
                name: {
                    "path": path,
                    "available": path is not None,
                }
                for name, path in self.tools.items()
            },
            "identities": {
                "developer_id_application": list(
                    self.developer_id_application_identities
                ),
                "developer_id_installer": list(
                    self.developer_id_installer_identities
                ),
            },
            "missing_tools": list(self.missing_tools),
            "missing_identities": list(self.missing_identities),
        }


def is_macos() -> bool:
    return platform.system().lower() == "darwin"


def macos_architecture() -> MacOSArchitectureSummary:
    machine = platform.machine().strip()
    processor = platform.processor().strip()
    normalized_machine = machine.lower()

    is_apple_silicon = normalized_machine in _APPLE_SILICON_MACHINES
    is_intel = normalized_machine in _INTEL_MACHINES
    if is_apple_silicon:
        kind = "apple_silicon"
    elif is_intel:
        kind = "intel"
    else:
        kind = "unknown"

    return MacOSArchitectureSummary(
        machine=machine,
        processor=processor,
        kind=kind,
        is_apple_silicon=is_apple_silicon,
        is_intel=is_intel,
    )


def common_app_support_paths(home: Path | None = None) -> MacOSAppSupportPaths:
    home_path = Path.home() if home is None else Path(home).expanduser()
    user_library = home_path / "Library"

    return MacOSAppSupportPaths(
        home=home_path,
        user_application_support=user_library / "Application Support",
        user_caches=user_library / "Caches",
        user_logs=user_library / "Logs",
        user_preferences=user_library / "Preferences",
        local_applications=Path("/Applications"),
        system_application_support=Path("/Library/Application Support"),
    )


def application_support_path(app_name: str, *, home: Path | None = None) -> Path:
    clean_name = app_name.strip()
    if not clean_name:
        raise ValueError("app_name must not be blank")

    return common_app_support_paths(home).user_application_support / clean_name


def python_runtime_summary() -> PythonRuntimeSummary:
    version_info = (
        sys.version_info.major,
        sys.version_info.minor,
        sys.version_info.micro,
        sys.version_info.releaselevel,
        sys.version_info.serial,
    )

    return PythonRuntimeSummary(
        executable=Path(sys.executable),
        version=sys.version,
        version_info=version_info,
        implementation=platform.python_implementation(),
        prefix=Path(sys.prefix),
        base_prefix=Path(sys.base_prefix),
        is_virtualenv=sys.prefix != sys.base_prefix,
    )


def macos_signing_readiness(
    *,
    which: ToolFinder | None = None,
    run_command: CommandRunner | None = None,
) -> MacOSSigningReadiness:
    """Return local readiness for Developer ID signing and notarization."""

    finder = shutil.which if which is None else which
    runner = _run_command if run_command is None else run_command
    tools = {
        "codesign": finder("codesign"),
        "productbuild": finder("productbuild"),
        "security": finder("security"),
        "notarytool": _find_notarytool(finder=finder, runner=runner),
    }
    application_identities: tuple[str, ...] = ()
    installer_identities: tuple[str, ...] = ()
    security_path = tools["security"]
    if security_path is not None:
        identities_output = _security_find_identities(
            security_path=security_path,
            runner=runner,
        )
        application_identities = _parse_developer_id_identities(
            identities_output,
            "Developer ID Application",
        )
        installer_identities = _parse_developer_id_identities(
            identities_output,
            "Developer ID Installer",
        )

    missing_tools = tuple(name for name, path in tools.items() if path is None)
    missing_identities = tuple(
        label
        for label, values in (
            ("Developer ID Application", application_identities),
            ("Developer ID Installer", installer_identities),
        )
        if not values
    )
    if missing_tools:
        status = "missing_tools"
    elif missing_identities:
        status = "missing_identities"
    else:
        status = "ready"

    return MacOSSigningReadiness(
        status=status,
        tools=tools,
        developer_id_application_identities=application_identities,
        developer_id_installer_identities=installer_identities,
        missing_tools=missing_tools,
        missing_identities=missing_identities,
    )


def macos_environment_report() -> JsonDict:
    architecture = macos_architecture()

    return {
        "platform": {
            "system": platform.system(),
            "is_macos": is_macos(),
            "release": platform.release(),
            "version": platform.version(),
            "mac_ver": platform.mac_ver()[0],
            "machine": architecture.machine,
            "processor": architecture.processor,
            "architecture": architecture.as_dict(),
        },
        "paths": common_app_support_paths().as_dict(),
        "python": python_runtime_summary().as_dict(),
        "signing": macos_signing_readiness().as_dict(),
    }


def _find_notarytool(*, finder: ToolFinder, runner: CommandRunner) -> str | None:
    direct_path = finder("notarytool")
    if direct_path is not None:
        return direct_path
    xcrun_path = finder("xcrun")
    if xcrun_path is None:
        return None
    result = runner([xcrun_path, "--find", "notarytool"])
    if result.returncode != 0:
        return None
    path = result.stdout.strip().splitlines()
    return path[0] if path else None


def _security_find_identities(*, security_path: str, runner: CommandRunner) -> str:
    result = runner([security_path, "find-identity", "-v", "-p", "codesigning"])
    if result.returncode != 0:
        return ""
    return result.stdout


def _parse_developer_id_identities(output: str, label: str) -> tuple[str, ...]:
    identities: list[str] = []
    prefix = f"{label}:"
    for line in output.splitlines():
        if prefix not in line or '"' not in line:
            continue
        quoted = line.split('"', 1)[1].rsplit('"', 1)[0]
        if quoted.startswith(prefix):
            identities.append(quoted)
    return tuple(identities)


def _run_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        text=True,
        capture_output=True,
        check=False,
    )


__all__ = [
    "MacOSAppSupportPaths",
    "MacOSArchitectureSummary",
    "MacOSSigningReadiness",
    "PythonRuntimeSummary",
    "application_support_path",
    "common_app_support_paths",
    "is_macos",
    "macos_architecture",
    "macos_environment_report",
    "macos_signing_readiness",
    "python_runtime_summary",
]
