"""Bambu profile source discovery and run artifact helpers."""

from __future__ import annotations

import hashlib
import os
import shutil
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from .core import load_profile

ProfileKey = tuple[str, str]
PROFILE_ROOT_ENV_VARS = (
    "PRINTPIPE_BAMBU_ORCA_PROFILE_ROOTS",
    "PRINTPIPE_BAMBU_PROFILE_ROOTS",
    "PRINTPIPE_PROFILE_ROOTS",
)
APPLICATIONS_DIR_ENV_VAR = "PRINTPIPE_APPLICATIONS_DIR"
PROFILE_SUBDIR_NAMES = frozenset({"filament", "process", "machine", "printer"})


class ProfileNotFoundError(FileNotFoundError):
    """Raised when a named profile cannot be found in a source index."""


@dataclass(frozen=True)
class ProfileSource:
    """Loaded profile JSON plus the path it came from."""

    name: str
    type: str
    path: Path
    source_root: Path
    relative_path: Path
    profile: Mapping[str, Any]


@dataclass(frozen=True)
class CopiedProfileArtifact:
    """Receipt-ready copy of one source profile in a run directory."""

    name: str
    type: str
    source_path: Path
    artifact_path: Path
    sha256: str

    def as_receipt_entry(self) -> dict[str, str]:
        """Return a stable JSON-serializable receipt entry."""
        return {
            "name": self.name,
            "type": self.type,
            "source_path": str(self.source_path),
            "artifact_path": str(self.artifact_path),
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class ProfileSourceIndex:
    """Profiles indexed by declared `(name, type)`.

    When the same `(name, type)` appears in multiple source roots, the first
    root wins. All matches are still retained for provenance and diagnostics.
    """

    roots: tuple[Path, ...]
    profiles: tuple[ProfileSource, ...]
    by_name_and_type: Mapping[ProfileKey, ProfileSource]
    matches_by_name_and_type: Mapping[ProfileKey, tuple[ProfileSource, ...]]

    def find(self, name: str, profile_type: str) -> ProfileSource:
        """Find the highest-priority profile matching `name` and `profile_type`."""
        key = _profile_key(name, profile_type)
        try:
            return self.by_name_and_type[key]
        except KeyError as exc:
            raise ProfileNotFoundError(_not_found_message(self, name, profile_type)) from exc

    def all_matches(self, name: str, profile_type: str) -> tuple[ProfileSource, ...]:
        """Return every matching profile in source-priority order."""
        return self.matches_by_name_and_type.get(_profile_key(name, profile_type), ())

    def profiles_for_type(self, profile_type: str) -> tuple[str, ...]:
        """Return known profile names for a type, sorted for stable diagnostics."""
        return tuple(
            sorted(
                {
                    name
                    for name, indexed_type in self.by_name_and_type
                    if indexed_type == profile_type
                }
            )
        )

    def profile_types(self) -> tuple[str, ...]:
        """Return known profile types sorted for stable diagnostics."""
        return tuple(sorted({profile_type for _, profile_type in self.by_name_and_type}))


def discover_profile_paths(roots: Iterable[str | Path]) -> list[Path]:
    """Discover profile JSON files recursively across source roots.

    Roots are searched in the order provided. Missing roots are skipped so a
    local cache can be preferred while an optional Bambu Studio install path is
    absent on CI or another machine.
    """
    return [path for _, path in _iter_profile_paths(roots)]


def default_bambu_orca_profile_roots(
    *,
    env: Mapping[str, str] | None = None,
    home: str | Path | None = None,
    platform: str | None = None,
) -> tuple[Path, ...]:
    """Return likely Bambu Studio and OrcaSlicer profile roots.

    Environment-provided roots take priority. Otherwise the candidates combine
    discovered user roots with platform-specific app-shipped default roots.
    """
    environ = os.environ if env is None else env
    platform_key = _platform_key(platform)
    env_roots = _profile_roots_from_env(environ, platform_key=platform_key)
    if env_roots:
        return env_roots

    if platform_key == "darwin":
        user_home = _home_path(home=home, env=environ)
        applications_dir = _optional_env_path(environ, APPLICATIONS_DIR_ENV_VAR) or Path(
            "/Applications"
        )
        return _dedupe_paths(
            (
                *_profile_user_roots(
                    user_home
                    / "Library"
                    / "Application Support"
                    / "BambuStudio"
                    / "user"
                ),
                *_profile_user_roots(
                    user_home
                    / "Library"
                    / "Application Support"
                    / "OrcaSlicer"
                    / "user"
                ),
                applications_dir
                / "BambuStudio.app"
                / "Contents"
                / "Resources"
                / "profiles"
                / "BBL",
                applications_dir
                / "OrcaSlicer.app"
                / "Contents"
                / "Resources"
                / "profiles",
            )
        )

    if platform_key == "windows":
        roots: list[Path] = []
        for base_path in _dedupe_paths(
            path
            for path in (
                _optional_env_path(environ, "APPDATA"),
                _optional_env_path(environ, "LOCALAPPDATA"),
            )
            if path is not None
        ):
            roots.extend(_profile_user_roots(base_path / "BambuStudio" / "user"))
            roots.extend(_profile_user_roots(base_path / "OrcaSlicer" / "user"))

        for install_root in _windows_install_roots(environ):
            roots.extend(
                (
                    install_root / "Bambu Studio" / "resources" / "profiles" / "BBL",
                    install_root / "BambuStudio" / "resources" / "profiles" / "BBL",
                    install_root / "OrcaSlicer" / "resources" / "profiles",
                    install_root / "Orca Slicer" / "resources" / "profiles",
                )
            )
        return _dedupe_paths(roots)

    return _dedupe_paths(
        (
            Path("/usr/share/bambu-studio/resources/profiles/BBL"),
            Path("/usr/local/share/bambu-studio/resources/profiles/BBL"),
            Path("/usr/share/orca-slicer/resources/profiles"),
            Path("/usr/local/share/orca-slicer/resources/profiles"),
        )
    )


def build_bambu_orca_filament_defaults_summary(
    roots: Iterable[str | Path] | None = None,
    *,
    env: Mapping[str, str] | None = None,
    home: str | Path | None = None,
    platform: str | None = None,
) -> dict[str, Any]:
    """Summarize discovered Bambu/Orca filament defaults as JSON-friendly data."""
    root_paths = _resolve_default_profile_roots(
        roots,
        env=env,
        home=home,
        platform=platform,
    )
    present_roots = tuple(root for root in root_paths if root.is_dir())

    profile_defaults: list[dict[str, Any]] = []
    skipped_profiles: list[dict[str, str]] = []
    seen_keys: set[ProfileKey] = set()

    for root, path in _iter_summary_profile_paths(present_roots):
        profile, skipped = _load_summary_profile(root, path)
        if skipped is not None:
            skipped_profiles.append(skipped)
            continue
        if profile is None:
            continue
        key = _profile_key(profile["name"], profile["type"])
        if key in seen_keys:
            continue
        seen_keys.add(key)
        profile_defaults.append(profile)

    filament_defaults = [
        _filament_summary(profile)
        for profile in profile_defaults
        if profile["type"] == "filament"
    ]
    profile_names_by_type = _profile_names_by_type(profile_defaults)
    filament_names_by_material = _filament_names_by_material(filament_defaults)

    return {
        "searched_roots": [str(root) for root in root_paths],
        "present_roots": [str(root) for root in present_roots],
        "missing_roots": [
            str(root)
            for root in root_paths
            if not root.is_dir()
        ],
        "missing": {
            "profile_roots": not present_roots,
            "filament_defaults": not filament_defaults,
        },
        "profile_names_by_type": profile_names_by_type,
        "filament_names_by_material": filament_names_by_material,
        "filament_defaults": filament_defaults,
        "profile_defaults": profile_defaults,
        "skipped_profiles": skipped_profiles,
    }


def load_profile_source_index(roots: Iterable[str | Path]) -> ProfileSourceIndex:
    """Load discovered profile JSON files and index them by declared name/type."""
    root_paths = tuple(Path(root) for root in roots)
    profiles: list[ProfileSource] = []
    first_match: dict[ProfileKey, ProfileSource] = {}
    all_matches: dict[ProfileKey, list[ProfileSource]] = defaultdict(list)

    for root, path in _iter_profile_paths(root_paths):
        profile = load_profile(path)
        name = _required_profile_text(profile, "name", path)
        profile_type = _required_profile_text(profile, "type", path)
        source = ProfileSource(
            name=name,
            type=profile_type,
            path=path,
            source_root=root,
            relative_path=path.relative_to(root),
            profile=profile,
        )
        profiles.append(source)

        key = _profile_key(name, profile_type)
        first_match.setdefault(key, source)
        all_matches[key].append(source)

    return ProfileSourceIndex(
        roots=root_paths,
        profiles=tuple(profiles),
        by_name_and_type=first_match,
        matches_by_name_and_type={
            key: tuple(matches) for key, matches in all_matches.items()
        },
    )


def find_profile_source(
    index_or_roots: ProfileSourceIndex | Iterable[str | Path],
    *,
    name: str,
    profile_type: str,
) -> ProfileSource:
    """Find a profile by name/type from an index or directly from roots."""
    if isinstance(index_or_roots, ProfileSourceIndex):
        index = index_or_roots
    else:
        index = load_profile_source_index(index_or_roots)
    return index.find(name, profile_type)


def copy_profile_source(
    source: ProfileSource,
    run_profiles_dir: str | Path,
) -> CopiedProfileArtifact:
    """Copy a source profile into a run's profiles directory and hash it."""
    destination_dir = Path(run_profiles_dir) / source.type
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / source.path.name

    shutil.copyfile(source.path, destination)
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    return CopiedProfileArtifact(
        name=source.name,
        type=source.type,
        source_path=source.path,
        artifact_path=destination,
        sha256=digest,
    )


def _resolve_default_profile_roots(
    roots: Iterable[str | Path] | None,
    *,
    env: Mapping[str, str] | None,
    home: str | Path | None,
    platform: str | None,
) -> tuple[Path, ...]:
    if roots is not None:
        return _dedupe_paths(Path(root) for root in roots)
    return default_bambu_orca_profile_roots(env=env, home=home, platform=platform)


def _profile_roots_from_env(
    env: Mapping[str, str],
    *,
    platform_key: str,
) -> tuple[Path, ...]:
    roots: list[Path] = []
    for key in PROFILE_ROOT_ENV_VARS:
        value = env.get(key)
        if not value:
            continue
        roots.extend(_split_env_paths(value, platform_key=platform_key))
    return _dedupe_paths(roots)


def _split_env_paths(value: str, *, platform_key: str) -> tuple[Path, ...]:
    separator = ";" if platform_key == "windows" else ":"
    return tuple(
        Path(part).expanduser()
        for part in value.split(separator)
        if part
    )


def _profile_user_roots(user_base: Path) -> tuple[Path, ...]:
    if not user_base.is_dir():
        return ()
    return tuple(
        sorted(
            (
                child
                for child in user_base.iterdir()
                if child.is_dir()
                and not child.name.startswith(".")
                and _looks_like_profile_root(child)
            ),
            key=_user_root_sort_key,
        )
    )


def _looks_like_profile_root(path: Path) -> bool:
    if any((path / name).is_dir() for name in PROFILE_SUBDIR_NAMES):
        return True
    return any(child.is_file() and child.suffix == ".json" for child in path.iterdir())


def _user_root_sort_key(path: Path) -> tuple[int, str]:
    if path.name.isdigit():
        return (0, path.name)
    if path.name == "default":
        return (1, path.name)
    return (2, path.name)


def _windows_install_roots(env: Mapping[str, str]) -> tuple[Path, ...]:
    local_appdata = _optional_env_path(env, "LOCALAPPDATA")
    roots = [
        _optional_env_path(env, "ProgramFiles"),
        _optional_env_path(env, "ProgramW6432"),
        local_appdata,
        local_appdata / "Programs" if local_appdata is not None else None,
    ]
    return _dedupe_paths(root for root in roots if root is not None)


def _iter_summary_profile_paths(roots: Iterable[Path]) -> Iterable[tuple[Path, Path]]:
    for root in roots:
        for path in sorted(root.rglob("*.json"), key=lambda item: str(item.relative_to(root))):
            if path.is_file():
                yield root, path


def _load_summary_profile(
    root: Path,
    path: Path,
) -> tuple[dict[str, Any] | None, dict[str, str] | None]:
    relative_path = path.relative_to(root)
    try:
        profile = load_profile(path)
    except ValueError as exc:
        return None, _skipped_profile(root, relative_path, path, str(exc))

    name = _optional_profile_text(profile, "name")
    profile_type = _optional_profile_text(profile, "type")
    if name is None or profile_type is None:
        return None, _skipped_profile(root, relative_path, path, "missing name or type")

    filament_types = _filament_types(profile)
    return {
        "name": name,
        "type": profile_type,
        "material": _first_or_none(filament_types),
        "filament_type": filament_types,
        "source_root": str(root),
        "relative_path": str(relative_path),
        "path": str(path),
        "from": _optional_profile_text(profile, "from"),
        "inherits": _optional_profile_text(profile, "inherits"),
        "filament_vendor": _string_list(profile.get("filament_vendor")),
    }, None


def _skipped_profile(
    root: Path,
    relative_path: Path,
    path: Path,
    reason: str,
) -> dict[str, str]:
    return {
        "path": str(path),
        "source_root": str(root),
        "relative_path": str(relative_path),
        "reason": reason,
    }


def _filament_summary(profile: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "name": profile["name"],
        "type": profile["type"],
        "material": profile["material"],
        "filament_type": profile["filament_type"],
        "source_root": profile["source_root"],
        "relative_path": profile["relative_path"],
        "path": profile["path"],
        "from": profile["from"],
        "inherits": profile["inherits"],
        "filament_vendor": profile["filament_vendor"],
    }


def _profile_names_by_type(
    profiles: Iterable[Mapping[str, Any]],
) -> dict[str, list[str]]:
    grouped: dict[str, set[str]] = defaultdict(set)
    for profile in profiles:
        grouped[str(profile["type"])].add(str(profile["name"]))
    return {
        profile_type: sorted(names)
        for profile_type, names in sorted(grouped.items())
    }


def _filament_names_by_material(
    filament_defaults: Iterable[Mapping[str, Any]],
) -> dict[str, list[str]]:
    grouped: dict[str, set[str]] = defaultdict(set)
    for profile in filament_defaults:
        materials = profile.get("filament_type")
        if not isinstance(materials, list) or not materials:
            continue
        for material in materials:
            grouped[str(material)].add(str(profile["name"]))
    return {
        material: sorted(names)
        for material, names in sorted(grouped.items())
    }


def _filament_types(profile: Mapping[str, Any]) -> list[str]:
    return _string_list(profile.get("filament_type"))


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item]
    return []


def _first_or_none(items: list[str]) -> str | None:
    return items[0] if items else None


def _optional_profile_text(profile: Mapping[str, Any], key: str) -> str | None:
    value = profile.get(key)
    if isinstance(value, str) and value:
        return value
    return None


def _iter_profile_paths(roots: Iterable[str | Path]) -> Iterable[tuple[Path, Path]]:
    for root in (Path(root) for root in roots):
        if not root.exists():
            continue
        if not root.is_dir():
            raise NotADirectoryError(f"profile source root is not a directory: {root}")
        for path in sorted(root.rglob("*.json"), key=lambda item: str(item.relative_to(root))):
            if path.is_file():
                yield root, path


def _required_profile_text(profile: Mapping[str, Any], key: str, path: Path) -> str:
    value = profile.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"profile JSON missing string {key}: {path}")
    return value


def _profile_key(name: str, profile_type: str) -> ProfileKey:
    return (name, profile_type)


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


def _not_found_message(index: ProfileSourceIndex, name: str, profile_type: str) -> str:
    searched = ", ".join(str(root) for root in index.roots) or "<no roots>"
    available = index.profiles_for_type(profile_type)
    if available:
        available_text = f"available {profile_type} profiles: {', '.join(available)}"
    else:
        profile_types = index.profile_types()
        type_text = ", ".join(profile_types) if profile_types else "none"
        available_text = f"available profile types: {type_text}"
    return (
        f"Could not find {profile_type} profile {name!r}; "
        f"searched: {searched}; {available_text}"
    )
