"""Windows packaging and runtime environment helpers.

The helpers in this module intentionally avoid Windows-only APIs so they can be
tested on macOS/Linux with injected environment mappings.
"""

from __future__ import annotations

import os
import platform
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

EnvMapping = Mapping[str, str]
PathExists = Callable[[str], bool]


@dataclass(frozen=True)
class WindowsPathCandidate:
    """One Windows path candidate plus the environment value that produced it."""

    kind: str
    path: str
    source: str

    def as_dict(self, *, path_exists: PathExists | None = None) -> dict[str, Any]:
        """Return a JSON-friendly representation of this candidate."""
        data: dict[str, Any] = {
            "kind": self.kind,
            "path": self.path,
            "source": self.source,
        }
        if path_exists is not None:
            data["exists"] = bool(path_exists(self.path))
        return data


def is_windows_platform(platform_name: str | None = None) -> bool:
    """Return whether `platform_name` represents a Windows runtime."""
    name = platform_name if platform_name is not None else sys.platform
    normalized = name.casefold()
    return normalized.startswith("win") or normalized in {"cygwin", "msys"}


def windows_appdata_candidates(env: EnvMapping | None = None) -> tuple[WindowsPathCandidate, ...]:
    """Return common Windows AppData roots from an injected or current environment."""
    environment = os.environ if env is None else env
    candidates: list[WindowsPathCandidate] = []
    seen: set[str] = set()

    for variable, kind in (
        ("APPDATA", "appdata_roaming"),
        ("LOCALAPPDATA", "appdata_local"),
        ("PROGRAMDATA", "program_data"),
    ):
        match = _env_path(environment, variable)
        if match is not None:
            source, path = match
            _append_candidate(candidates, seen, kind=kind, path=path, source=source)

    user_profile = _env_path(environment, "USERPROFILE")
    if user_profile is not None:
        source, home = user_profile
        _append_candidate(
            candidates,
            seen,
            kind="appdata_roaming",
            path=_join_path(home, "AppData", "Roaming"),
            source=source,
        )
        _append_candidate(
            candidates,
            seen,
            kind="appdata_local",
            path=_join_path(home, "AppData", "Local"),
            source=source,
        )

    return tuple(candidates)


def windows_program_files_candidates(
    env: EnvMapping | None = None,
) -> tuple[WindowsPathCandidate, ...]:
    """Return common Windows Program Files roots from an injected or current environment."""
    environment = os.environ if env is None else env
    candidates: list[WindowsPathCandidate] = []
    seen: set[str] = set()

    for variable, kind in (
        ("ProgramFiles", "program_files"),
        ("ProgramFiles(x86)", "program_files_x86"),
        ("ProgramW6432", "program_files_w6432"),
    ):
        match = _env_path(environment, variable)
        if match is not None:
            source, path = match
            _append_candidate(candidates, seen, kind=kind, path=path, source=source)

    return tuple(candidates)


def python_runtime_summary(
    *,
    executable: str | None = None,
    version_info: Sequence[Any] | None = None,
    implementation: str | None = None,
) -> dict[str, Any]:
    """Return a JSON-friendly Python executable/version summary."""
    version = sys.version_info if version_info is None else version_info
    major = int(version[0])
    minor = int(version[1])
    micro = int(version[2])
    releaselevel = str(version[3]) if len(version) > 3 else "final"
    serial = int(version[4]) if len(version) > 4 else 0

    return {
        "executable": executable if executable is not None else sys.executable,
        "implementation": (
            implementation if implementation is not None else platform.python_implementation()
        ),
        "version": f"{major}.{minor}.{micro}",
        "version_info": {
            "major": major,
            "minor": minor,
            "micro": micro,
            "releaselevel": releaselevel,
            "serial": serial,
        },
    }


def windows_environment_report(
    *,
    env: EnvMapping | None = None,
    platform_name: str | None = None,
    executable: str | None = None,
    version_info: Sequence[Any] | None = None,
    implementation: str | None = None,
    path_exists: PathExists | None = None,
) -> dict[str, Any]:
    """Return a JSON-friendly Windows packaging/runtime environment report."""
    environment = os.environ if env is None else env
    current_platform = platform_name if platform_name is not None else sys.platform
    exists = os.path.exists if path_exists is None else path_exists

    return {
        "platform": current_platform,
        "is_windows": is_windows_platform(current_platform),
        "python": python_runtime_summary(
            executable=executable,
            version_info=version_info,
            implementation=implementation,
        ),
        "paths": {
            "appdata": [
                candidate.as_dict(path_exists=exists)
                for candidate in windows_appdata_candidates(environment)
            ],
            "program_files": [
                candidate.as_dict(path_exists=exists)
                for candidate in windows_program_files_candidates(environment)
            ],
        },
    }


def _env_path(env: EnvMapping, variable: str) -> tuple[str, str] | None:
    if variable in env:
        path = _clean_path(env[variable])
        if path is not None:
            return variable, path

    variable_key = variable.casefold()
    for key, value in env.items():
        if key.casefold() != variable_key:
            continue
        path = _clean_path(value)
        if path is not None:
            return key, path
    return None


def _clean_path(value: str) -> str | None:
    path = os.fspath(value).strip().strip('"')
    return path or None


def _append_candidate(
    candidates: list[WindowsPathCandidate],
    seen: set[str],
    *,
    kind: str,
    path: str,
    source: str,
) -> None:
    key = _path_key(path)
    if key in seen:
        return
    candidates.append(WindowsPathCandidate(kind=kind, path=path, source=source))
    seen.add(key)


def _path_key(path: str) -> str:
    return path.rstrip("\\/").casefold()


def _join_path(base: str, *parts: str) -> str:
    separator = "\\" if "\\" in base else "/"
    return base.rstrip("\\/") + separator + separator.join(parts)
