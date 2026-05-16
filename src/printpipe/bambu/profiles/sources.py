"""Bambu profile source discovery and run artifact helpers."""

from __future__ import annotations

import hashlib
import shutil
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from .core import load_profile

ProfileKey = tuple[str, str]


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
