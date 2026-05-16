"""Bambu Studio installation candidate discovery.

The helpers in this module only report likely install locations. They do not
launch Bambu Studio or shell out, which keeps discovery deterministic and safe
for unit tests.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterable, Mapping

CandidateReport = dict[str, bool | list[str] | str]

_MACOS_APP_BUNDLE_NAMES: tuple[str, ...] = (
    "Bambu Studio.app",
    "BambuStudio.app",
)
_WINDOWS_INSTALL_DIR_NAMES: tuple[str, ...] = (
    "Bambu Studio",
    "BambuStudio",
)
_WINDOWS_EXECUTABLE_NAMES: tuple[str, ...] = (
    "bambu-studio.exe",
    "Bambu Studio.exe",
    "BambuStudio.exe",
)


def detect_bambu_studio_candidates(
    *,
    platform: str | None = None,
    roots: Iterable[str | Path] | None = None,
    env: Mapping[str, str] | None = None,
) -> list[CandidateReport]:
    """Return likely Bambu Studio install candidates for the selected platform."""

    normalized_platform = _normalize_platform(platform or sys.platform)
    if normalized_platform == "macos":
        return macos_bambu_studio_candidates(roots=roots, env=env)
    if normalized_platform == "windows":
        return windows_bambu_studio_candidates(roots=roots, env=env)
    return []


def macos_bambu_studio_candidates(
    *,
    roots: Iterable[str | Path] | None = None,
    env: Mapping[str, str] | None = None,
    include_user_applications: bool = False,
) -> list[CandidateReport]:
    """Return macOS app bundle candidates in stable search order."""

    candidate_roots = list(_path_roots(roots))
    if roots is None:
        candidate_roots.append(Path("/Applications"))
        include_user_applications = True

    if include_user_applications:
        home = _env(env).get("HOME")
        if home:
            candidate_roots.append(Path(home) / "Applications")

    return [
        _candidate_report(
            path=root / bundle_name,
            platform="macos",
            launch_hint_prefix=("open",),
            open_hint_prefix=("open", "-a"),
        )
        for root in _dedupe_paths(candidate_roots)
        for bundle_name in _MACOS_APP_BUNDLE_NAMES
    ]


def windows_bambu_studio_candidates(
    *,
    roots: Iterable[str | Path] | None = None,
    env: Mapping[str, str] | None = None,
) -> list[CandidateReport]:
    """Return Windows executable candidates in stable search order."""

    candidate_roots = list(_path_roots(roots))
    if roots is None:
        env_values = _env(env)
        for key in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)", "LOCALAPPDATA"):
            value = env_values.get(key)
            if value:
                if key == "LOCALAPPDATA":
                    candidate_roots.append(Path(value) / "Programs")
                else:
                    candidate_roots.append(Path(value))

    return [
        _candidate_report(
            path=root / directory_name / executable_name,
            platform="windows",
            launch_hint_prefix=(),
            open_hint_prefix=(),
        )
        for root in _dedupe_paths(candidate_roots)
        for directory_name in _WINDOWS_INSTALL_DIR_NAMES
        for executable_name in _WINDOWS_EXECUTABLE_NAMES
    ]


def _candidate_report(
    *,
    path: Path,
    platform: str,
    launch_hint_prefix: tuple[str, ...],
    open_hint_prefix: tuple[str, ...],
) -> CandidateReport:
    path_text = str(path)
    return {
        "path": path_text,
        "platform": platform,
        "exists": path.exists(),
        "launch_hint": [*launch_hint_prefix, path_text],
        "open_hint": [*open_hint_prefix, path_text, "<file.3mf>"],
    }


def _normalize_platform(platform: str) -> str:
    platform_text = platform.lower()
    if platform_text in {"darwin", "mac", "macos", "osx"}:
        return "macos"
    if platform_text in {"win32", "cygwin", "msys", "nt", "windows"}:
        return "windows"
    return platform_text


def _path_roots(roots: Iterable[str | Path] | None) -> tuple[Path, ...]:
    if roots is None:
        return ()
    return tuple(Path(root).expanduser() for root in roots)


def _env(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


def _dedupe_paths(paths: Iterable[Path]) -> tuple[Path, ...]:
    deduped: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(path)
    return tuple(deduped)
