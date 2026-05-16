"""Geometry artifact writers for dependency-light mesh orientation."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from printpipe.contracts import Artifact, ArtifactKind, StageReceipt, StageStatus
from printpipe.geometry.core import (
    Bounds3D,
    Vertex3D,
    apply_uniform_scale,
    center_xy_drop_z,
    compute_bounds,
    rotate_z,
)


Triangle = tuple[Vertex3D, Vertex3D, Vertex3D]


def read_ascii_stl_vertices(input_path: str | Path) -> tuple[Vertex3D, ...]:
    """Read vertices from a simple ASCII STL file."""
    triangles = _read_ascii_stl_triangles(Path(input_path))
    return tuple(vertex for triangle in triangles for vertex in triangle)


def write_oriented_ascii_stl_artifacts(
    input_path: str | Path,
    output_dir: str | Path,
    *,
    scale_factor: float = 1.0,
    rotation_degrees: float = 0.0,
    stem: str | None = None,
) -> StageReceipt:
    """Orient a simple ASCII STL, write mesh plus JSON sidecar, and return a receipt."""
    source_path = Path(input_path)
    output_path = Path(output_dir)

    try:
        if scale_factor <= 0.0:
            raise ValueError("scale_factor must be positive")
        source_triangles = _read_ascii_stl_triangles(source_path)
    except ValueError as exc:
        return StageReceipt(
            stage="geometry.write_oriented_ascii_stl_artifacts",
            status=StageStatus.FAILED,
            message=str(exc),
            metrics={
                "input_path": str(source_path),
                "scale_factor": scale_factor,
                "rotation_degrees": rotation_degrees,
            },
        )

    source_vertices = tuple(vertex for triangle in source_triangles for vertex in triangle)
    source_bounds = compute_bounds(source_vertices)
    transformed_vertices = center_xy_drop_z(
        rotate_z(apply_uniform_scale(source_vertices, scale_factor), rotation_degrees)
    )
    oriented_bounds = compute_bounds(transformed_vertices)
    oriented_triangles = _group_triangles(transformed_vertices)

    output_path.mkdir(parents=True, exist_ok=True)
    mesh_stem = stem if stem is not None else f"{source_path.stem}_oriented"
    sidecar_stem = f"{stem}_orientation" if stem is not None else f"{source_path.stem}_orientation"
    mesh_path = output_path / f"{mesh_stem}.stl"
    sidecar_path = output_path / f"{sidecar_stem}.json"

    _write_ascii_stl(mesh_path, mesh_stem, oriented_triangles)

    mesh_artifact = Artifact(
        kind=ArtifactKind.ORIENTED_MESH,
        path=mesh_path,
        label="Oriented ASCII STL mesh",
        metadata={
            "format": "ascii_stl",
            "source_path": str(source_path),
        },
    )
    sidecar_artifact = Artifact(
        kind=ArtifactKind.REPORT,
        path=sidecar_path,
        label="Orientation JSON receipt",
        metadata={"format": "json"},
    )
    metrics: dict[str, Any] = {
        "input_format": "ascii_stl",
        "scale_factor": float(scale_factor),
        "rotation_degrees": float(rotation_degrees),
        "transform_order": "scale_then_rotate_z_then_center_xy_drop_z",
        "triangle_count": len(oriented_triangles),
        "vertex_count": len(transformed_vertices),
        "source_bounds_mm": _bounds_to_dict(source_bounds),
        "oriented_bounds_mm": _bounds_to_dict(oriented_bounds),
    }
    payload = {
        "input_path": str(source_path),
        "output_mesh_path": str(mesh_path),
        "metrics": metrics,
        "artifacts": (
            _artifact_to_dict(mesh_artifact),
            _artifact_to_dict(sidecar_artifact),
        ),
        "heuristics": {
            "basis": "ascii_stl_vertices_only",
            "semantic_claim": False,
        },
    }
    sidecar_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    return StageReceipt(
        stage="geometry.write_oriented_ascii_stl_artifacts",
        status=StageStatus.SUCCEEDED,
        message="wrote oriented ASCII STL mesh and orientation sidecar",
        artifacts=(mesh_artifact, sidecar_artifact),
        metrics=metrics,
    )


def _read_ascii_stl_triangles(input_path: Path) -> tuple[Triangle, ...]:
    if input_path.suffix.lower() != ".stl":
        raise ValueError("only ASCII .stl inputs are supported")
    try:
        raw = input_path.read_bytes()
    except FileNotFoundError as exc:
        raise ValueError(f"input mesh does not exist: {input_path}") from exc
    if b"\x00" in raw:
        raise ValueError("only ASCII .stl inputs are supported; binary data was detected")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("only ASCII .stl inputs are supported; file is not UTF-8 text") from exc

    stripped = text.lstrip()
    if not stripped.lower().startswith("solid"):
        raise ValueError("only ASCII .stl inputs are supported; missing solid header")

    vertices: list[Vertex3D] = []
    for line in text.splitlines():
        parts = line.strip().split()
        if len(parts) == 4 and parts[0].lower() == "vertex":
            try:
                vertices.append((float(parts[1]), float(parts[2]), float(parts[3])))
            except ValueError as exc:
                raise ValueError(f"invalid ASCII STL vertex line: {line.strip()}") from exc

    if not vertices:
        raise ValueError("ASCII STL input does not contain any vertices")
    if len(vertices) % 3 != 0:
        raise ValueError("ASCII STL vertex count must be divisible by 3")
    return _group_triangles(tuple(vertices))


def _group_triangles(vertices: tuple[Vertex3D, ...]) -> tuple[Triangle, ...]:
    if len(vertices) % 3 != 0:
        raise ValueError("vertex count must be divisible by 3")
    return tuple(
        (vertices[index], vertices[index + 1], vertices[index + 2])
        for index in range(0, len(vertices), 3)
    )


def _write_ascii_stl(output_path: Path, solid_name: str, triangles: tuple[Triangle, ...]) -> None:
    lines = [f"solid {solid_name}"]
    for triangle in triangles:
        normal = _triangle_normal(triangle)
        lines.append(
            f"  facet normal {_format_float(normal[0])} {_format_float(normal[1])} {_format_float(normal[2])}"
        )
        lines.append("    outer loop")
        for x, y, z in triangle:
            lines.append(f"      vertex {_format_float(x)} {_format_float(y)} {_format_float(z)}")
        lines.append("    endloop")
        lines.append("  endfacet")
    lines.append(f"endsolid {solid_name}")
    lines.append("")
    output_path.write_text("\n".join(lines), encoding="utf-8")


def _triangle_normal(triangle: Triangle) -> Vertex3D:
    (ax, ay, az), (bx, by, bz), (cx, cy, cz) = triangle
    ux, uy, uz = bx - ax, by - ay, bz - az
    vx, vy, vz = cx - ax, cy - ay, cz - az
    nx = (uy * vz) - (uz * vy)
    ny = (uz * vx) - (ux * vz)
    nz = (ux * vy) - (uy * vx)
    length = math.sqrt((nx * nx) + (ny * ny) + (nz * nz))
    if length == 0.0:
        return (0.0, 0.0, 0.0)
    return (_clean_float(nx / length), _clean_float(ny / length), _clean_float(nz / length))


def _bounds_to_dict(bounds: Bounds3D) -> dict[str, float]:
    return {
        "min_x": bounds.min_x,
        "min_y": bounds.min_y,
        "min_z": bounds.min_z,
        "max_x": bounds.max_x,
        "max_y": bounds.max_y,
        "max_z": bounds.max_z,
        "width_x": bounds.width_x,
        "depth_y": bounds.depth_y,
        "height_z": bounds.height_z,
    }


def _artifact_to_dict(artifact: Artifact) -> dict[str, Any]:
    return {
        "kind": artifact.kind.value,
        "path": str(artifact.path),
        "label": artifact.label,
        "metadata": artifact.metadata,
    }


def _format_float(value: float) -> str:
    cleaned = _clean_float(value)
    if float(cleaned).is_integer():
        return str(int(cleaned))
    return f"{cleaned:.12g}"


def _clean_float(value: float) -> float:
    if math.isclose(value, 0.0, abs_tol=1e-12):
        return 0.0
    nearest_int = round(value)
    if math.isclose(value, nearest_int, abs_tol=1e-12):
        return float(nearest_int)
    return value

