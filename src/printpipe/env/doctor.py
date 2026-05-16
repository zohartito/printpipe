"""Unified environment doctor report for local PrintPipe installs."""

from __future__ import annotations

import os
import sys
from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from printpipe.env.bambu_profiles import build_bambu_profile_detection_report
from printpipe.env.bambu_studio import detect_bambu_studio_candidates
from printpipe.env.dependencies import check_dependency_preflight
from printpipe.env.macos import macos_environment_report
from printpipe.env.windows import windows_environment_report


def build_environment_report(
    *,
    platform_name: str | None = None,
    env: Mapping[str, str] | None = None,
    home: str | Path | None = None,
    bambu_studio_roots: Iterable[str | Path] | None = None,
    profile_base_paths: Iterable[str | Path] | None = None,
) -> dict[str, Any]:
    """Build one JSON-friendly environment report for `printpipe doctor`."""

    environment = os.environ if env is None else env
    raw_platform = platform_name or sys.platform
    platform_key = normalize_platform(raw_platform)
    dependencies = check_dependency_preflight(environ=environment)
    studio_candidates = detect_bambu_studio_candidates(
        platform=raw_platform,
        roots=bambu_studio_roots,
        env=environment,
    )
    profile_report = build_bambu_profile_detection_report(
        base_paths=profile_base_paths,
        platform=_profile_platform(raw_platform, platform_key),
        env=environment,
        home=home,
    )

    return {
        "schema_version": 1,
        "platform": {
            "raw": raw_platform,
            "normalized": platform_key,
        },
        "system": _system_report(platform_key, raw_platform, environment),
        "dependencies": dependencies,
        "bambu_studio": {
            "candidate_count": len(studio_candidates),
            "installed_count": sum(1 for candidate in studio_candidates if candidate["exists"]),
            "candidates": studio_candidates,
        },
        "bambu_profiles": profile_report,
        "summary": {
            "dependency_status_counts": dict(Counter(report["status"] for report in dependencies)),
            "bambu_studio_found": any(candidate["exists"] for candidate in studio_candidates),
            "bambu_profile_user_count": profile_report["candidate_count"],
        },
    }


def render_environment_report(report: Mapping[str, Any]) -> str:
    """Render a concise human-readable doctor report."""

    platform_info = _mapping(report.get("platform"))
    summary = _mapping(report.get("summary"))
    studio = _mapping(report.get("bambu_studio"))
    profiles = _mapping(report.get("bambu_profiles"))
    dependencies = _list(report.get("dependencies"))

    lines = [
        "PrintPipe Doctor",
        f"Platform: {platform_info.get('normalized', 'unknown')} ({platform_info.get('raw', 'unknown')})",
        "",
        "Dependencies:",
    ]
    if dependencies:
        for dependency in dependencies:
            item = _mapping(dependency)
            lines.append(
                "- "
                f"{item.get('status', 'unknown')}: "
                f"{item.get('label', item.get('id', 'dependency'))} - "
                f"{item.get('action', '')}"
            )
    else:
        lines.append("- none reported")

    lines.extend(
        [
            "",
            (
                "Bambu Studio: "
                f"{studio.get('installed_count', 0)} installed candidate(s) / "
                f"{studio.get('candidate_count', 0)} checked"
            ),
            f"Bambu profile users: {profiles.get('candidate_count', 0)}",
            (
                "Dependency statuses: "
                + ", ".join(
                    f"{key}={value}"
                    for key, value in sorted(
                        _mapping(summary.get("dependency_status_counts")).items()
                    )
                )
            ),
            "",
        ]
    )
    return "\n".join(lines)


def normalize_platform(platform_name: str) -> str:
    """Normalize Python platform names for report sections."""

    value = platform_name.lower()
    if value in {"darwin", "mac", "macos", "osx"}:
        return "macos"
    if value.startswith("win") or value in {"cygwin", "msys", "nt", "windows"}:
        return "windows"
    return value


def _system_report(
    platform_key: str,
    raw_platform: str,
    env: Mapping[str, str],
) -> dict[str, Any]:
    if platform_key == "macos":
        return macos_environment_report()
    if platform_key == "windows":
        return windows_environment_report(env=env, platform_name=raw_platform)
    return {}


def _profile_platform(raw_platform: str, platform_key: str) -> str:
    if platform_key == "macos":
        return "darwin"
    if platform_key == "windows":
        return "win32"
    return raw_platform


def _mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


def _list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


__all__ = [
    "build_environment_report",
    "normalize_platform",
    "render_environment_report",
]
