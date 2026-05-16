from __future__ import annotations

import platform
import sys
from dataclasses import dataclass
from pathlib import Path

JsonDict = dict[str, object]

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
    }


__all__ = [
    "MacOSAppSupportPaths",
    "MacOSArchitectureSummary",
    "PythonRuntimeSummary",
    "application_support_path",
    "common_app_support_paths",
    "is_macos",
    "macos_architecture",
    "macos_environment_report",
    "python_runtime_summary",
]
