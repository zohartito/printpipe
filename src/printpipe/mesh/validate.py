"""Mesh topology validation and receipt export."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from printpipe.contracts import MeshStats
from printpipe.mesh.topology import (
    count_boundary_edges,
    count_inconsistent_winding_edges,
    count_non_manifold_edges,
    count_face_edges,
    infer_vertices_count,
    normalize_faces,
)


@dataclass(frozen=True)
class MeshValidationResult:
    """Result of a dependency-light topology scan."""

    stats: MeshStats
    defects: tuple[str, ...] = ()
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return not self.defects

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "stats": {
                "vertices": self.stats.vertices,
                "faces": self.stats.faces,
                "watertight": self.stats.watertight,
                "euler_number": self.stats.euler_number,
                "boundary_edges": self.stats.boundary_edges,
                "non_manifold_edges": self.stats.non_manifold_edges,
                "bounds_mm": self.stats.bounds_mm,
            },
            "defects": list(self.defects),
            "diagnostics": dict(self.diagnostics),
        }


class MeshValidationError(ValueError):
    """Raised when a mesh topology gate fails."""

    def __init__(self, result: MeshValidationResult) -> None:
        self.result = result
        defect_summary = ", ".join(result.defects) or "unknown topology defect"
        super().__init__(f"mesh topology validation failed: {defect_summary}")


def validate_mesh_topology(
    faces: Iterable[Sequence[int]],
    *,
    vertices_count: int | None = None,
) -> MeshValidationResult:
    """Validate triangle topology from index triples."""
    normalized_faces = normalize_faces(faces)
    if vertices_count is None:
        vertices_count = infer_vertices_count(normalized_faces)
    if vertices_count < 0:
        raise ValueError("vertices_count must be non-negative")

    edge_counts = count_face_edges(normalized_faces)
    boundary_edges = count_boundary_edges(edge_counts)
    non_manifold_edges = count_non_manifold_edges(edge_counts)
    inconsistent_winding_edges = count_inconsistent_winding_edges(normalized_faces)
    unique_edges = len(edge_counts)
    watertight = bool(normalized_faces) and boundary_edges == 0 and non_manifold_edges == 0
    euler_number = vertices_count - unique_edges + len(normalized_faces)

    defects: list[str] = []
    if boundary_edges:
        defects.append(_pluralize(boundary_edges, "boundary edge"))
    if non_manifold_edges:
        defects.append(_pluralize(non_manifold_edges, "non-manifold edge"))
    if inconsistent_winding_edges:
        defects.append(_pluralize(inconsistent_winding_edges, "inconsistent winding edge"))

    return MeshValidationResult(
        stats=MeshStats(
            vertices=vertices_count,
            faces=len(normalized_faces),
            watertight=watertight,
            euler_number=euler_number,
            boundary_edges=boundary_edges,
            non_manifold_edges=non_manifold_edges,
        ),
        defects=tuple(defects),
        diagnostics={
            "inconsistent_winding_edges": inconsistent_winding_edges,
            "normal_orientation": _normal_orientation(
                watertight=watertight,
                inconsistent_winding_edges=inconsistent_winding_edges,
            ),
        },
    )


def gate_mesh_topology(
    faces: Iterable[Sequence[int]],
    *,
    vertices_count: int | None = None,
    stats_path: Path,
) -> MeshValidationResult:
    """Write mesh topology stats JSON and fail on hard topology defects."""
    result = validate_mesh_topology(faces, vertices_count=vertices_count)
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    stats_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n")
    if not result.passed:
        raise MeshValidationError(result)
    return result


def _pluralize(count: int, singular: str) -> str:
    suffix = "" if count == 1 else "s"
    return f"{count} {singular}{suffix}"


def _normal_orientation(*, watertight: bool, inconsistent_winding_edges: int) -> str:
    if inconsistent_winding_edges:
        return "inconsistent"
    if watertight:
        return "consistent"
    return "unknown"
