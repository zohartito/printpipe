"""Flex-coupon STL generator for flexible-material validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from printpipe.contracts import Artifact, ArtifactKind, StageReceipt, StageStatus


DEFAULT_LENGTH_MM = 40.0
DEFAULT_WIDTH_MM = 15.0
DEFAULT_HEIGHT_MM = 3.0
DEFAULT_STEM = "flex_coupon_40x15x3"
PRINT_VALIDATION_POINTS = (
    "bed adhesion",
    "flex recovery",
    "interlayer bonding",
    "support/brim removability",
)
Vertex = tuple[float, float, float]
Triangle = tuple[Vertex, Vertex, Vertex]


def write_flex_coupon_artifacts(
    output_dir: str | Path,
    *,
    material: str,
    use_case: str,
    length_mm: float = DEFAULT_LENGTH_MM,
    width_mm: float = DEFAULT_WIDTH_MM,
    height_mm: float = DEFAULT_HEIGHT_MM,
    stem: str = DEFAULT_STEM,
) -> StageReceipt:
    """Write a small rectangular ASCII STL coupon and JSON sidecar."""

    output_path = Path(output_dir)
    mesh_path = output_path / f"{stem}.stl"
    sidecar_path = output_path / f"{stem}.json"

    try:
        dimensions = _validate_dimensions(length_mm, width_mm, height_mm)
    except ValueError as exc:
        return StageReceipt(
            stage="validation.flex_coupon",
            status=StageStatus.FAILED,
            message=str(exc),
            metrics={
                "length_mm": length_mm,
                "width_mm": width_mm,
                "height_mm": height_mm,
            },
        )

    output_path.mkdir(parents=True, exist_ok=True)
    triangles = _box_triangles(*dimensions)
    _write_ascii_stl(mesh_path, stem, triangles)
    sidecar = {
        "artifact": mesh_path.name,
        "dimensions_mm": {
            "length": dimensions[0],
            "width": dimensions[1],
            "height": dimensions[2],
        },
        "format": "ascii_stl",
        "material": material,
        "print_validation": list(PRINT_VALIDATION_POINTS),
        "stage": "validation.flex_coupon",
        "use_case": use_case,
    }
    sidecar_path.write_text(json.dumps(sidecar, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    mesh_artifact = Artifact(
        kind=ArtifactKind.CALIBRATION_MESH,
        path=mesh_path,
        label="Flex coupon ASCII STL",
        metadata={
            "dimensions_mm": sidecar["dimensions_mm"],
            "material": material,
            "use_case": use_case,
        },
    )
    report_artifact = Artifact(
        kind=ArtifactKind.REPORT,
        path=sidecar_path,
        label="Flex coupon JSON receipt",
        metadata={"format": "json"},
    )
    return StageReceipt(
        stage="validation.flex_coupon",
        status=StageStatus.SUCCEEDED,
        message="wrote flexible-material validation coupon",
        artifacts=(mesh_artifact, report_artifact),
        metrics={
            "length_mm": dimensions[0],
            "width_mm": dimensions[1],
            "height_mm": dimensions[2],
            "triangle_count": len(triangles),
        },
    )


def _validate_dimensions(length_mm: float, width_mm: float, height_mm: float) -> tuple[float, float, float]:
    dimensions = (float(length_mm), float(width_mm), float(height_mm))
    if any(value <= 0.0 for value in dimensions):
        raise ValueError("flex coupon dimensions must be positive")
    return dimensions


def _box_triangles(length_mm: float, width_mm: float, height_mm: float) -> tuple[Triangle, ...]:
    x0 = -length_mm / 2.0
    x1 = length_mm / 2.0
    y0 = -width_mm / 2.0
    y1 = width_mm / 2.0
    z0 = 0.0
    z1 = height_mm
    vertices = {
        "000": (x0, y0, z0),
        "100": (x1, y0, z0),
        "110": (x1, y1, z0),
        "010": (x0, y1, z0),
        "001": (x0, y0, z1),
        "101": (x1, y0, z1),
        "111": (x1, y1, z1),
        "011": (x0, y1, z1),
    }
    return (
        (vertices["000"], vertices["100"], vertices["110"]),
        (vertices["000"], vertices["110"], vertices["010"]),
        (vertices["001"], vertices["011"], vertices["111"]),
        (vertices["001"], vertices["111"], vertices["101"]),
        (vertices["000"], vertices["001"], vertices["101"]),
        (vertices["000"], vertices["101"], vertices["100"]),
        (vertices["100"], vertices["101"], vertices["111"]),
        (vertices["100"], vertices["111"], vertices["110"]),
        (vertices["110"], vertices["111"], vertices["011"]),
        (vertices["110"], vertices["011"], vertices["010"]),
        (vertices["010"], vertices["011"], vertices["001"]),
        (vertices["010"], vertices["001"], vertices["000"]),
    )


def _write_ascii_stl(output_path: Path, solid_name: str, triangles: tuple[Triangle, ...]) -> None:
    lines = [f"solid {solid_name}"]
    for triangle in triangles:
        normal = _normal(triangle)
        lines.append(
            "  facet normal "
            f"{_format_float(normal[0])} {_format_float(normal[1])} {_format_float(normal[2])}"
        )
        lines.append("    outer loop")
        for vertex in triangle:
            lines.append(
                "      vertex "
                f"{_format_float(vertex[0])} {_format_float(vertex[1])} {_format_float(vertex[2])}"
            )
        lines.append("    endloop")
        lines.append("  endfacet")
    lines.append(f"endsolid {solid_name}")
    lines.append("")
    output_path.write_text("\n".join(lines), encoding="ascii")


def _normal(triangle: Triangle) -> Vertex:
    (ax, ay, az), (bx, by, bz), (cx, cy, cz) = triangle
    ux, uy, uz = bx - ax, by - ay, bz - az
    vx, vy, vz = cx - ax, cy - ay, cz - az
    nx = uy * vz - uz * vy
    ny = uz * vx - ux * vz
    nz = ux * vy - uy * vx
    length = (nx * nx + ny * ny + nz * nz) ** 0.5
    if length == 0.0:
        return (0.0, 0.0, 0.0)
    return (nx / length, ny / length, nz / length)


def _format_float(value: Any) -> str:
    return f"{float(value):.6f}".rstrip("0").rstrip(".") or "0"
