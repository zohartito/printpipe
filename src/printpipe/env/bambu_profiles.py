"""Bambu Studio user profile directory discovery helpers."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

PROFILE_SUBFOLDER_NAMES: Mapping[str, tuple[str, ...]] = {
    "filament": ("filament",),
    "process": ("process",),
    "printer": ("machine", "printer"),
}


@dataclass(frozen=True)
class BambuProfileSubfolder:
    """Known profile-kind subfolder found under a Bambu Studio user directory."""

    kind: str
    folder_name: str
    path: Path
    json_file_count: int

    def as_report(self) -> dict[str, Any]:
        """Return a JSON-serializable report for this subfolder."""
        return {
            "kind": self.kind,
            "folder_name": self.folder_name,
            "path": str(self.path),
            "json_file_count": self.json_file_count,
        }


@dataclass(frozen=True)
class BambuUserProfileCandidate:
    """Candidate `BambuStudio/user/<user-id>` profile directory."""

    user_id: str
    path: Path
    base_path: Path
    subfolders: Mapping[str, tuple[BambuProfileSubfolder, ...]]

    def profile_kinds(self) -> tuple[str, ...]:
        """Return profile kinds with at least one detected subfolder."""
        return tuple(
            kind
            for kind in PROFILE_SUBFOLDER_NAMES
            if self.subfolders.get(kind)
        )

    def as_report(self) -> dict[str, Any]:
        """Return a JSON-serializable report for this user profile candidate."""
        return {
            "user_id": self.user_id,
            "path": str(self.path),
            "base_path": str(self.base_path),
            "profile_kinds": list(self.profile_kinds()),
            "subfolders": {
                kind: [
                    subfolder.as_report()
                    for subfolder in self.subfolders.get(kind, ())
                ]
                for kind in PROFILE_SUBFOLDER_NAMES
            },
        }


def default_bambu_user_base_paths(
    *,
    platform: str | None = None,
    env: Mapping[str, str] | None = None,
    home: str | Path | None = None,
) -> tuple[Path, ...]:
    """Return likely `BambuStudio/user` roots for the current or injected platform."""
    platform_key = _platform_key(platform)
    environ = os.environ if env is None else env

    if platform_key == "darwin":
        user_home = _home_path(home=home, env=environ)
        return (
            user_home
            / "Library"
            / "Application Support"
            / "BambuStudio"
            / "user",
        )

    if platform_key == "windows":
        roots = [
            _optional_env_path(environ, "APPDATA"),
            _optional_env_path(environ, "LOCALAPPDATA"),
        ]
        return _dedupe_paths(
            root / "BambuStudio" / "user"
            for root in roots
            if root is not None
        )

    return ()


def discover_bambu_user_profile_candidates(
    base_paths: Iterable[str | Path] | None = None,
    *,
    platform: str | None = None,
    env: Mapping[str, str] | None = None,
    home: str | Path | None = None,
) -> tuple[BambuUserProfileCandidate, ...]:
    """Discover candidate Bambu Studio user profile directories.

    Bambu Studio stores cloud-synced user data below paths shaped like
    `BambuStudio/user/<cloud-user-id>`. The user-id folder is intentionally not
    constrained to a single known account so local, cloud, and fixture IDs all
    report through the same foundation.
    """
    resolved_base_paths = _resolve_base_paths(
        base_paths,
        platform=platform,
        env=env,
        home=home,
    )
    candidates: list[BambuUserProfileCandidate] = []

    for base_path in resolved_base_paths:
        if not base_path.is_dir():
            continue
        for user_path in sorted(base_path.iterdir(), key=lambda path: path.name):
            if not user_path.is_dir() or user_path.name.startswith("."):
                continue
            candidates.append(
                BambuUserProfileCandidate(
                    user_id=user_path.name,
                    path=user_path,
                    base_path=base_path,
                    subfolders=_discover_profile_subfolders(user_path),
                )
            )

    return tuple(candidates)


def build_bambu_profile_detection_report(
    base_paths: Iterable[str | Path] | None = None,
    *,
    platform: str | None = None,
    env: Mapping[str, str] | None = None,
    home: str | Path | None = None,
) -> dict[str, Any]:
    """Build a JSON-friendly Bambu Studio profile discovery report."""
    resolved_base_paths = _resolve_base_paths(
        base_paths,
        platform=platform,
        env=env,
        home=home,
    )
    candidates = discover_bambu_user_profile_candidates(base_paths=resolved_base_paths)

    return {
        "platform": _platform_key(platform),
        "base_paths": [
            {
                "path": str(base_path),
                "exists": base_path.exists(),
                "is_dir": base_path.is_dir(),
                "user_ids": [
                    candidate.user_id
                    for candidate in candidates
                    if candidate.base_path == base_path
                ],
            }
            for base_path in resolved_base_paths
        ],
        "candidate_count": len(candidates),
        "profile_subfolder_names": {
            kind: list(folder_names)
            for kind, folder_names in PROFILE_SUBFOLDER_NAMES.items()
        },
        "candidates": [candidate.as_report() for candidate in candidates],
    }


def _resolve_base_paths(
    base_paths: Iterable[str | Path] | None,
    *,
    platform: str | None,
    env: Mapping[str, str] | None,
    home: str | Path | None,
) -> tuple[Path, ...]:
    if base_paths is not None:
        return _dedupe_paths(Path(path) for path in base_paths)
    return default_bambu_user_base_paths(platform=platform, env=env, home=home)


def _discover_profile_subfolders(
    user_path: Path,
) -> Mapping[str, tuple[BambuProfileSubfolder, ...]]:
    subfolders: dict[str, tuple[BambuProfileSubfolder, ...]] = {}
    for kind, folder_names in PROFILE_SUBFOLDER_NAMES.items():
        found = []
        for folder_name in folder_names:
            subfolder_path = user_path / folder_name
            if subfolder_path.is_dir():
                found.append(
                    BambuProfileSubfolder(
                        kind=kind,
                        folder_name=folder_name,
                        path=subfolder_path,
                        json_file_count=_count_json_files(subfolder_path),
                    )
                )
        subfolders[kind] = tuple(found)
    return subfolders


def _count_json_files(path: Path) -> int:
    return sum(1 for child in path.iterdir() if child.is_file() and child.suffix == ".json")


def _platform_key(platform: str | None) -> str:
    raw_platform = sys.platform if platform is None else platform
    if raw_platform == "darwin":
        return "darwin"
    if raw_platform.startswith("win") or raw_platform in {"cygwin", "msys"}:
        return "windows"
    return raw_platform


def _home_path(*, home: str | Path | None, env: Mapping[str, str]) -> Path:
    if home is not None:
        return Path(home).expanduser()
    env_home = env.get("HOME")
    if env_home:
        return Path(env_home).expanduser()
    return Path.home()


def _optional_env_path(env: Mapping[str, str], key: str) -> Path | None:
    value = env.get(key)
    if not value:
        return None
    return Path(value).expanduser()


def _dedupe_paths(paths: Iterable[Path]) -> tuple[Path, ...]:
    deduped: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = os.fspath(path)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(path)
    return tuple(deduped)
