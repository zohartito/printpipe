"""Local run artifact discovery and download-link helpers."""

from __future__ import annotations

import json
import mimetypes
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote


CATEGORY_ORIGINAL_INPUT = "original_input"
CATEGORY_REPORTS = "reports"
CATEGORY_GENERATED_MESH = "generated_mesh"
CATEGORY_REPAIRED_MESH = "repaired_mesh"
CATEGORY_BUNDLE = "bundle"
CATEGORY_SLICE_LOG = "slice_log"
CATEGORY_PREVIEW = "preview"

CATEGORY_ORDER: tuple[str, ...] = (
    CATEGORY_ORIGINAL_INPUT,
    CATEGORY_REPORTS,
    CATEGORY_GENERATED_MESH,
    CATEGORY_REPAIRED_MESH,
    CATEGORY_BUNDLE,
    CATEGORY_SLICE_LOG,
    CATEGORY_PREVIEW,
)


@dataclass(frozen=True)
class ArtifactLink:
    """Safe descriptor for rendering or serving a local run artifact."""

    category: str
    label: str
    path: str
    href: str
    download_name: str
    media_type: str
    size_bytes: int


def discover_run_artifacts(
    run_root: Path,
    *,
    link_base: str = "/artifacts/",
) -> tuple[ArtifactLink, ...]:
    """Discover primary local artifact links for a run.

    The returned tuple is ordered by ``CATEGORY_ORDER`` and then by category
    priority. Report-declared artifacts are preferred, with filesystem fallbacks
    for still-useful run outputs. Duplicate paths are collapsed.
    """

    root = _resolve_root(run_root)
    candidates: list[_Candidate] = []

    report = _load_report(root)
    for order, artifact in enumerate(_iter_report_artifacts(report)):
        kind = _as_text(artifact.get("kind"))
        category = _category_for_kind(kind)
        if category is None:
            continue

        artifact_path = artifact.get("path")
        if artifact_path is None:
            continue

        label = _as_text(artifact.get("label")) or _default_label(category)
        candidates.append(
            _Candidate(
                category=category,
                path=artifact_path,
                label=label,
                priority=_priority(category, artifact_path, label),
                order=order,
            )
        )

    fallback_start = len(candidates)
    for offset, candidate in enumerate(_fallback_candidates(root)):
        candidates.append(
            _Candidate(
                category=candidate.category,
                path=candidate.path,
                label=candidate.label,
                priority=20 + candidate.priority,
                order=fallback_start + offset,
            )
        )

    selected: dict[str, tuple[int, int, int, ArtifactLink]] = {}
    for candidate in candidates:
        try:
            link = link_for_artifact(
                root,
                candidate.path,
                category=candidate.category,
                label=candidate.label,
                link_base=link_base,
            )
        except (FileNotFoundError, ValueError):
            continue

        category_index = CATEGORY_ORDER.index(candidate.category)
        rank = (category_index, candidate.priority, candidate.order)
        current = selected.get(link.path)
        if current is None or rank < current[:3]:
            selected[link.path] = (*rank, link)

    return tuple(
        ranked_link[3]
        for ranked_link in sorted(selected.values(), key=lambda item: item[:3])
    )


def link_for_artifact(
    run_root: Path,
    artifact_path: str | Path,
    *,
    category: str,
    label: str | None = None,
    link_base: str = "/artifacts/",
) -> ArtifactLink:
    """Build a safe web descriptor for an existing artifact under ``run_root``."""

    root = _resolve_root(run_root)
    resolved_path = _resolve_artifact_path(root, artifact_path)
    if not resolved_path.is_file():
        raise FileNotFoundError(resolved_path)

    relative_path = resolved_path.relative_to(root).as_posix()
    download_name = resolved_path.name
    return ArtifactLink(
        category=category,
        label=label or _default_label(category),
        path=relative_path,
        href=_href_for_relative_path(relative_path, link_base=link_base),
        download_name=download_name,
        media_type=_media_type(resolved_path),
        size_bytes=resolved_path.stat().st_size,
    )


def resolve_artifact_request(run_root: Path, request_path: str | Path) -> Path:
    """Convert a web request path into a file path under ``run_root``.

    Percent-encoded traversal and symlink escapes are rejected by resolving the
    candidate path before checking that it remains inside the resolved run root.
    """

    root = _resolve_root(run_root)
    path_text = _normalize_request_path(request_path)
    candidate = Path(path_text)
    if not candidate.is_absolute():
        candidate = root / candidate

    resolved_path = candidate.expanduser().resolve()
    _ensure_inside_run_root(root, resolved_path)
    if not resolved_path.is_file():
        raise FileNotFoundError(resolved_path)
    return resolved_path


@dataclass(frozen=True)
class _Candidate:
    category: str
    path: str | Path
    label: str
    priority: int
    order: int = 0


_KIND_TO_CATEGORY = {
    "original_input": CATEGORY_ORIGINAL_INPUT,
    "report": CATEGORY_REPORTS,
    "generated_mesh": CATEGORY_GENERATED_MESH,
    "repaired_mesh": CATEGORY_REPAIRED_MESH,
    "3mf": CATEGORY_BUNDLE,
    "slice_log": CATEGORY_SLICE_LOG,
    "preview": CATEGORY_PREVIEW,
}

_DEFAULT_LABELS = {
    CATEGORY_ORIGINAL_INPUT: "Original input",
    CATEGORY_REPORTS: "Run report",
    CATEGORY_GENERATED_MESH: "Generated mesh",
    CATEGORY_REPAIRED_MESH: "Repaired mesh",
    CATEGORY_BUNDLE: "Bambu bundle",
    CATEGORY_SLICE_LOG: "Slice log",
    CATEGORY_PREVIEW: "Preview",
}

_MEDIA_TYPES = {
    ".3mf": "model/3mf",
    ".gltf": "model/gltf+json",
    ".glb": "model/gltf-binary",
    ".log": "text/plain",
    ".md": "text/markdown",
    ".obj": "model/obj",
    ".stl": "model/stl",
}


def _resolve_root(run_root: Path) -> Path:
    return run_root.expanduser().resolve()


def _resolve_artifact_path(root: Path, artifact_path: str | Path) -> Path:
    if isinstance(artifact_path, Path):
        candidate = artifact_path.expanduser()
    else:
        artifact_text = artifact_path
        if "\x00" in artifact_text:
            raise ValueError("artifact path contains null byte")
        candidate = Path(artifact_text).expanduser()

    if not candidate.is_absolute():
        candidate = root / candidate

    resolved_path = candidate.resolve()
    _ensure_inside_run_root(root, resolved_path)
    return resolved_path


def _ensure_inside_run_root(root: Path, path: Path) -> None:
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"artifact path is outside run root: {path}") from exc


def _normalize_request_path(request_path: str | Path) -> str:
    path_text = str(request_path)
    if "\x00" in path_text:
        raise ValueError("artifact path contains null byte")
    return unquote(path_text).replace("\\", "/")


def _href_for_relative_path(relative_path: str, *, link_base: str) -> str:
    quoted_path = quote(relative_path, safe="/.")
    if not link_base:
        return quoted_path
    separator = "" if link_base.endswith("/") else "/"
    return f"{link_base}{separator}{quoted_path}"


def _load_report(root: Path) -> Mapping[str, Any]:
    report_path = root / "80_reports" / "run_report.json"
    if not report_path.is_file():
        return {}
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if isinstance(report, Mapping):
        return report
    return {}


def _iter_report_artifacts(report: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    top_level = report.get("artifacts", ())
    yield from _iter_artifact_mappings(top_level)

    stages = report.get("stages", ())
    if not isinstance(stages, list | tuple):
        return
    for stage in stages:
        if isinstance(stage, Mapping):
            yield from _iter_artifact_mappings(stage.get("artifacts", ()))


def _iter_artifact_mappings(value: Any) -> Iterable[Mapping[str, Any]]:
    if not isinstance(value, list | tuple):
        return
    for item in value:
        if isinstance(item, Mapping):
            yield item


def _fallback_candidates(root: Path) -> Iterable[_Candidate]:
    yield from _fallback_existing(
        root,
        CATEGORY_REPORTS,
        (
            "80_reports/run_report.html",
            "80_reports/run_report.md",
            "80_reports/run_report.json",
        ),
    )
    yield from _fallback_glob(
        root,
        CATEGORY_ORIGINAL_INPUT,
        "00_input/*",
    )
    yield from _fallback_glob(
        root,
        CATEGORY_GENERATED_MESH,
        "20_meshgen/*",
        suffixes={".3mf", ".glb", ".gltf", ".obj", ".stl"},
    )
    yield from _fallback_glob(
        root,
        CATEGORY_REPAIRED_MESH,
        "30_repair/*",
        suffixes={".3mf", ".glb", ".gltf", ".obj", ".stl"},
    )
    yield from _fallback_glob(
        root,
        CATEGORY_BUNDLE,
        "60_bundle/*.3mf",
    )
    yield from _fallback_glob(
        root,
        CATEGORY_SLICE_LOG,
        "70_slice/*",
        suffixes={".log", ".txt"},
    )
    yield from _fallback_glob(
        root,
        CATEGORY_PREVIEW,
        "80_reports/*",
        suffixes={".gif", ".jpeg", ".jpg", ".png", ".webp"},
    )
    yield from _fallback_glob(
        root,
        CATEGORY_PREVIEW,
        "40_geometry/*",
        suffixes={".gif", ".jpeg", ".jpg", ".png", ".webp"},
    )


def _fallback_existing(
    root: Path,
    category: str,
    relative_paths: Iterable[str],
) -> Iterable[_Candidate]:
    for order, relative_path in enumerate(relative_paths):
        path = root / relative_path
        if path.is_file():
            yield _Candidate(
                category=category,
                path=path,
                label=_default_label(category),
                priority=order,
            )


def _fallback_glob(
    root: Path,
    category: str,
    pattern: str,
    *,
    suffixes: set[str] | None = None,
) -> Iterable[_Candidate]:
    for path in sorted(root.glob(pattern), key=lambda candidate: candidate.as_posix()):
        if not path.is_file():
            continue
        if suffixes is not None and path.suffix.lower() not in suffixes:
            continue
        label = _label_for_path(category, path)
        yield _Candidate(
            category=category,
            path=path,
            label=label,
            priority=_priority(category, path, label),
        )


def _category_for_kind(kind: str) -> str | None:
    return _KIND_TO_CATEGORY.get(kind)


def _default_label(category: str) -> str:
    return _DEFAULT_LABELS.get(category, "Artifact")


def _label_for_path(category: str, path: Path) -> str:
    if category == CATEGORY_REPORTS:
        if path.suffix == ".html":
            return "Run report HTML"
        if path.suffix == ".md":
            return "Run report Markdown"
        if path.suffix == ".json":
            return "Run report JSON"
    if category == CATEGORY_PREVIEW and _looks_like_bed_fit(path):
        return "Bed fit preview"
    return _default_label(category)


def _priority(category: str, path: str | Path, label: str) -> int:
    path_text = Path(str(path)).as_posix().lower()
    label_text = label.lower()
    if category == CATEGORY_REPORTS:
        suffix = Path(path_text).suffix
        return {".html": 0, ".md": 1, ".json": 2}.get(suffix, 5)
    if category == CATEGORY_PREVIEW:
        return 0 if _looks_like_bed_fit_text(f"{path_text} {label_text}") else 5
    if category == CATEGORY_BUNDLE:
        return 0 if path_text.endswith(".3mf") else 5
    return 0


def _looks_like_bed_fit(path: Path) -> bool:
    return _looks_like_bed_fit_text(path.as_posix())


def _looks_like_bed_fit_text(text: str) -> bool:
    lowered = text.lower()
    return "bed" in lowered or "fit" in lowered


def _media_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in _MEDIA_TYPES:
        return _MEDIA_TYPES[suffix]
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


def _as_text(value: Any) -> str:
    return "" if value is None else str(value)


__all__ = [
    "ArtifactLink",
    "CATEGORY_BUNDLE",
    "CATEGORY_GENERATED_MESH",
    "CATEGORY_ORIGINAL_INPUT",
    "CATEGORY_ORDER",
    "CATEGORY_PREVIEW",
    "CATEGORY_REPAIRED_MESH",
    "CATEGORY_REPORTS",
    "CATEGORY_SLICE_LOG",
    "discover_run_artifacts",
    "link_for_artifact",
    "resolve_artifact_request",
]
