"""Optional trimesh-backed mesh repair."""

from __future__ import annotations

import importlib
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from printpipe.contracts import MeshStats, StageStatus
from printpipe.mesh.topology import (
    count_boundary_edges,
    count_face_edges,
    count_non_manifold_edges,
)


class MeshRepairUnavailableError(RuntimeError):
    """Raised when the optional mesh repair dependency is not installed."""


class MeshRepairError(RuntimeError):
    """Raised when mesh repair runs but does not satisfy the repair gate."""

    def __init__(self, result: MeshRepairResult) -> None:
        self.result = result
        super().__init__(result.message)


@dataclass(frozen=True)
class MeshRepairResult:
    """Receipt-style result for a mesh repair attempt."""

    before: MeshStats
    after: MeshStats
    output_path: Path
    status: StageStatus
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "before": _mesh_stats_to_dict(self.before),
            "after": _mesh_stats_to_dict(self.after),
            "output_path": str(self.output_path),
            "status": self.status.value,
            "message": self.message,
        }


def repair_mesh_file(
    input_path: Path | str,
    output_path: Path | str,
    *,
    allow_non_watertight: bool = False,
) -> MeshRepairResult:
    """Repair a mesh file with trimesh and export the repaired mesh."""
    trimesh = _import_trimesh()
    input_path = Path(input_path)
    output_path = Path(output_path)

    mesh = _load_mesh(trimesh, input_path)
    before = _mesh_stats(mesh)
    repaired = _repair_mesh(trimesh, mesh)
    after = _mesh_stats(repaired)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    repaired.export(output_path)

    if after.watertight:
        return MeshRepairResult(
            before=before,
            after=after,
            output_path=output_path,
            status=StageStatus.SUCCEEDED,
            message=f"Repaired mesh written to {output_path}.",
        )

    result = MeshRepairResult(
        before=before,
        after=after,
        output_path=output_path,
        status=StageStatus.FAILED,
        message=(
            f"repair failed: {output_path} is still non-watertight "
            f"({after.boundary_edges} boundary edges, "
            f"{after.non_manifold_edges} non-manifold edges)"
        ),
    )
    if allow_non_watertight:
        return result
    raise MeshRepairError(result)


def _import_trimesh() -> Any:
    try:
        return importlib.import_module("trimesh")
    except ImportError as exc:
        raise MeshRepairUnavailableError(
            "Mesh repair requires the optional 'trimesh' package. "
            "Install trimesh to enable repair_mesh_file()."
        ) from exc


def _load_mesh(trimesh: Any, input_path: Path) -> Any:
    mesh = trimesh.load(input_path, force="mesh", process=False)
    if not isinstance(mesh, trimesh.Trimesh):
        raise TypeError(f"{input_path} did not load as a single mesh")
    return mesh


def _repair_mesh(trimesh: Any, mesh: Any) -> Any:
    repaired = mesh.copy()
    repaired.merge_vertices()

    _remove_duplicate_faces(repaired)
    _remove_degenerate_faces(repaired)
    repaired.remove_unreferenced_vertices()

    if not repaired.is_watertight:
        trimesh.repair.fill_holes(repaired)
        repaired.remove_unreferenced_vertices()

    trimesh.repair.fix_normals(repaired)
    return repaired


def _remove_duplicate_faces(mesh: Any) -> None:
    if hasattr(mesh, "unique_faces") and hasattr(mesh, "update_faces"):
        mesh.update_faces(mesh.unique_faces())
        return
    if hasattr(mesh, "remove_duplicate_faces"):
        mesh.remove_duplicate_faces()


def _remove_degenerate_faces(mesh: Any) -> None:
    if hasattr(mesh, "nondegenerate_faces") and hasattr(mesh, "update_faces"):
        mesh.update_faces(mesh.nondegenerate_faces())
        return
    if hasattr(mesh, "remove_degenerate_faces"):
        mesh.remove_degenerate_faces()


def _mesh_stats(mesh: Any) -> MeshStats:
    faces = _int_faces(mesh.faces)
    edge_counts = count_face_edges(faces)
    euler_number = getattr(mesh, "euler_number", None)
    if euler_number is not None:
        euler_number = int(euler_number)

    return MeshStats(
        vertices=len(mesh.vertices),
        faces=len(faces),
        watertight=bool(mesh.is_watertight),
        euler_number=euler_number,
        boundary_edges=count_boundary_edges(edge_counts),
        non_manifold_edges=count_non_manifold_edges(edge_counts),
        bounds_mm=_mesh_extents(mesh),
    )


def _int_faces(faces: Iterable[Sequence[Any]]) -> tuple[tuple[int, int, int], ...]:
    return tuple((int(face[0]), int(face[1]), int(face[2])) for face in faces)


def _mesh_extents(mesh: Any) -> tuple[float, float, float] | None:
    if len(mesh.vertices) == 0:
        return None
    return tuple(float(value) for value in mesh.extents)


def _mesh_stats_to_dict(stats: MeshStats) -> dict[str, Any]:
    return {
        "vertices": stats.vertices,
        "faces": stats.faces,
        "watertight": stats.watertight,
        "euler_number": stats.euler_number,
        "boundary_edges": stats.boundary_edges,
        "non_manifold_edges": stats.non_manifold_edges,
        "bounds_mm": stats.bounds_mm,
    }
