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
    workspace_paths: Iterable[str | Path] | None = None,
    artifact_paths: Iterable[str | Path] | None = None,
) -> dict[str, Any]:
    """Build one JSON-friendly environment report for `printpipe doctor`."""

    from printpipe.meshgen import build_media_meshgen_readiness

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
    filesystem_checks = _filesystem_checks(
        workspace_paths=workspace_paths,
        artifact_paths=artifact_paths,
        env=environment,
    )
    meshgen_env = None if env is None else environment
    meshgen = build_media_meshgen_readiness(env=meshgen_env)

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
        "filesystem": {"checks": filesystem_checks},
        "meshgen": meshgen,
        "summary": {
            "dependency_status_counts": dict(Counter(report["status"] for report in dependencies)),
            "filesystem_status_counts": dict(
                Counter(check["status"] for check in filesystem_checks)
            ),
            "bambu_studio_found": any(candidate["exists"] for candidate in studio_candidates),
            "bambu_profile_user_count": profile_report["candidate_count"],
            "meshgen_status": meshgen["overall_status"],
            "live_media_meshgen_provider_count": meshgen["live_media_provider_count"],
        },
    }


def render_environment_report(report: Mapping[str, Any]) -> str:
    """Render a concise human-readable doctor report."""

    platform_info = _mapping(report.get("platform"))
    summary = _mapping(report.get("summary"))
    system = _mapping(report.get("system"))
    signing = _mapping(system.get("signing"))
    studio = _mapping(report.get("bambu_studio"))
    profiles = _mapping(report.get("bambu_profiles"))
    meshgen = _mapping(report.get("meshgen"))
    dependencies = _list(report.get("dependencies"))
    filesystem_checks = _list(_mapping(report.get("filesystem")).get("checks"))

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

    lines.extend(["", "Filesystem:"])
    if filesystem_checks:
        for check in filesystem_checks:
            item = _mapping(check)
            lines.append(
                "- "
                f"{item.get('status', 'unknown')}: "
                f"{item.get('label', item.get('id', 'path'))} - "
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
                "Media meshgen: "
                f"{meshgen.get('overall_status', 'unknown')} "
                f"({meshgen.get('live_media_provider_count', 0)} live provider(s))"
            ),
            (
                "Dependency statuses: "
                + ", ".join(
                    f"{key}={value}"
                    for key, value in sorted(
                        _mapping(summary.get("dependency_status_counts")).items()
                    )
                )
            ),
        ]
    )
    if signing:
        signing_label = (
            "Windows installer signing"
            if platform_info.get("normalized") == "windows"
            else "macOS signing"
        )
        lines.extend(
            [
                "",
                f"{signing_label}: {signing.get('status', 'unknown')}",
                "Missing signing tools: "
                + _join_or_none(_list(signing.get("missing_tools"))),
                "Missing signing identities: "
                + _join_or_none(_list(signing.get("missing_identities"))),
            ]
        )
    lines.append("")
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


def _filesystem_checks(
    *,
    workspace_paths: Iterable[str | Path] | None,
    artifact_paths: Iterable[str | Path] | None,
    env: Mapping[str, str],
) -> list[dict[str, Any]]:
    workspaces = list(workspace_paths) if workspace_paths is not None else [Path.cwd()]
    artifacts = (
        list(artifact_paths)
        if artifact_paths is not None
        else _paths_from_env(env.get("PRINTPIPE_ARTIFACT_PATHS", ""))
    )

    checks: list[dict[str, Any]] = []
    checks.extend(
        _filesystem_check(kind="workspace", index=index, path=path)
        for index, path in enumerate(workspaces)
    )
    checks.extend(
        _filesystem_check(kind="artifact", index=index, path=path)
        for index, path in enumerate(artifacts)
    )
    return checks


def _paths_from_env(value: str) -> list[Path]:
    return [Path(item).expanduser() for item in value.split(os.pathsep) if item]


def _filesystem_check(
    *,
    kind: str,
    index: int,
    path: str | Path,
) -> dict[str, Any]:
    resolved_path = Path(path).expanduser().resolve()
    label = "Workspace path" if kind == "workspace" else "Artifact path"
    exists = _safe_exists(resolved_path)
    readable = exists and _can_read_path(resolved_path)
    status = "ok" if exists and readable else "warning"

    if not exists:
        action = "Confirm the path exists or update the configured location."
    elif not readable:
        action = (
            "Grant filesystem permission or move the path somewhere PrintPipe can read."
        )
    else:
        action = "No action needed."

    return {
        "id": f"{kind}:{index}",
        "kind": kind,
        "label": label,
        "path": str(resolved_path),
        "exists": exists,
        "readable": readable,
        "status": status,
        "action": action,
    }


def _safe_exists(path: Path) -> bool:
    try:
        return path.exists()
    except OSError:
        return False


def _can_read_path(path: Path) -> bool:
    try:
        if path.is_dir():
            with os.scandir(path):
                pass
        else:
            with path.open("rb") as handle:
                handle.read(0)
    except OSError:
        return False
    return True


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


def _join_or_none(values: list[Any]) -> str:
    return ", ".join(str(item) for item in values) or "none"


__all__ = [
    "build_environment_report",
    "normalize_platform",
    "render_environment_report",
]
