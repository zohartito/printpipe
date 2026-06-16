"""Deterministic fabrication-verification geometry functions."""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from printpipe.fabrication.report import OrientationCandidate, PackingResult, PartResult
from printpipe.mesh.validate import validate_mesh_topology

EPSILON = 1e-9
PRINT_PLATE_MM = (250.0, 250.0)
LASER_SHEET_MM = (12.0 * 25.4, 12.0 * 25.4)


def thicken_to_solids(shells: Iterable[Any], wall_mm: float) -> list[PartResult]:
    """Offset open triangle shells into closed solids, retrying the opposite side.

    Already-solid inputs are passed through as valid parts with ``thicken_dir_mm``
    set to ``None``. Open shells try ``+wall_mm`` first, then ``-wall_mm`` when
    the first offset is invalid or flipped.
    """

    if wall_mm <= 0:
        raise ValueError("wall_mm must be positive")

    results: list[PartResult] = []
    for index, shell in enumerate(shells):
        part_id = _part_id(shell, index)
        mesh = _mesh_from(shell)
        source_faces = _source_faces(shell, mesh)
        if mesh is None:
            results.append(
                PartResult(
                    id=part_id,
                    source_faces=source_faces,
                    thicken_dir_mm=None,
                    solid=False,
                    valid=False,
                    failure_reason="un-thickenable: no mesh geometry available",
                )
            )
            continue

        existing = _validate_mesh_part(mesh, part_id=part_id, thicken_dir_mm=None)
        if existing.valid:
            results.append(existing)
            continue

        failures: list[str] = []
        for direction in (float(wall_mm), -float(wall_mm)):
            try:
                solid_mesh = _offset_open_triangle_shell(mesh, direction)
            except ValueError as exc:
                failures.append(f"{_format_mm(direction)}: {exc}")
                continue
            candidate = _validate_mesh_part(
                solid_mesh,
                part_id=part_id,
                thicken_dir_mm=_clean(direction),
            )
            if candidate.valid:
                results.append(candidate)
                break
            failures.append(
                f"{_format_mm(direction)}: {candidate.failure_reason or 'invalid offset solid'}"
            )
        else:
            detail = "; ".join(failures) if failures else existing.failure_reason
            results.append(
                PartResult(
                    id=part_id,
                    source_faces=source_faces,
                    thicken_dir_mm=None,
                    solid=False,
                    valid=False,
                    failure_reason=f"un-thickenable: {detail}",
                )
            )

    return results


def validate(parts: Iterable[Any]) -> list[PartResult]:
    """Validate parts as closed, manifold, positive-volume solids."""

    results: list[PartResult] = []
    for index, part in enumerate(parts):
        if isinstance(part, PartResult) and _mesh_from(part) is None:
            results.append(part)
            continue
        part_id = _part_id(part, index)
        mesh = _mesh_from(part)
        if mesh is None:
            results.append(
                PartResult(
                    id=part_id,
                    source_faces=_source_faces(part, None),
                    thicken_dir_mm=_thicken_dir(part),
                    solid=False,
                    valid=False,
                    failure_reason="no mesh geometry available",
                )
            )
            continue
        results.append(
            _validate_mesh_part(mesh, part_id=part_id, thicken_dir_mm=_thicken_dir(part))
        )
    return results


def score_orientations(part: Any) -> list[OrientationCandidate]:
    """Score flat-vs-upright orientation candidates from deterministic bounds."""

    width, depth, height = _part_extents_mm(part)
    if min(width, depth, height) <= 0:
        raise ValueError("part extents must be positive")

    dims = sorted((float(width), float(depth), float(height)))
    thickness, middle, longest = dims
    volume = width * depth * height
    max_face_area = max(width * depth, width * height, depth * height)

    flat_base = longest * middle
    upright_base = longest * thickness
    flat = _orientation_candidate(
        "flat_outer_face",
        volume=volume,
        base_area=flat_base,
        max_face_area=max_face_area,
        support_fraction=0.02,
        show_face_quality=0.95,
    )
    upright = _orientation_candidate(
        "upright_edge_on_bed",
        volume=volume,
        base_area=upright_base,
        max_face_area=max_face_area,
        support_fraction=0.35,
        show_face_quality=0.70,
    )
    return sorted((flat, upright), key=lambda item: (-item.score, item.name))


def pack(parts: Iterable[Any], unit: str) -> PackingResult:
    """Shelf-pack valid parts into print plates or laser sheets and center each unit."""

    unit_label, unit_width, unit_depth = _unit_dimensions_mm(unit)
    pack_units: list[dict[str, Any]] = []
    unplaced: list[str] = []
    total_area = 0.0

    for index, part in enumerate(parts):
        part_id = _part_id(part, index)
        if not _part_is_valid(part):
            unplaced.append(part_id)
            continue
        try:
            width, depth, _height = _part_extents_mm(part)
        except ValueError:
            unplaced.append(part_id)
            continue

        orientations = _packing_orientations(width, depth)
        if not any(w <= unit_width + EPSILON and d <= unit_depth + EPSILON for w, d, _ in orientations):
            unplaced.append(part_id)
            continue

        placement = None
        for pack_unit in pack_units:
            placement = _try_place_in_unit(
                pack_unit,
                part_id=part_id,
                orientations=orientations,
                unit_width=unit_width,
                unit_depth=unit_depth,
            )
            if placement is not None:
                break

        if placement is None:
            pack_unit = _new_pack_unit(len(pack_units) + 1)
            pack_units.append(pack_unit)
            placement = _try_place_in_unit(
                pack_unit,
                part_id=part_id,
                orientations=orientations,
                unit_width=unit_width,
                unit_depth=unit_depth,
            )
        if placement is None:
            unplaced.append(part_id)
            if pack_units and not pack_units[-1]["placements"]:
                pack_units.pop()
            continue
        total_area += width * depth

    layout: list[dict] = []
    for pack_unit in pack_units:
        layout.extend(_centered_layout(pack_unit, unit_width=unit_width, unit_depth=unit_depth))

    units_used = len([pack_unit for pack_unit in pack_units if pack_unit["placements"]])
    efficiency = total_area / (units_used * unit_width * unit_depth) if units_used else 0.0
    return PackingResult(
        unit=unit_label,
        units_used=units_used,
        layout=layout,
        efficiency=efficiency,
        unplaced=unplaced,
    )


def _validate_mesh_part(mesh: Any, *, part_id: str, thicken_dir_mm: float | None) -> PartResult:
    vertices = _vertices(mesh)
    faces = _faces(mesh)
    source_faces = len(faces)
    defects: list[str] = []

    if not vertices:
        defects.append("empty mesh vertices")
    if not faces:
        defects.append("empty mesh faces")

    degenerate_faces = _count_degenerate_faces(vertices, faces) if vertices and faces else 0
    if degenerate_faces:
        defects.append(_pluralize(degenerate_faces, "degenerate face"))

    topology = None
    if faces:
        try:
            topology = validate_mesh_topology(faces, vertices=vertices if vertices else None)
        except (TypeError, ValueError) as exc:
            defects.append(str(exc))
        else:
            defects.extend(topology.defects)

    component_count = _component_count(mesh)
    if component_count > 1:
        defects.append(_pluralize(component_count, "disconnected component"))

    volume = _mesh_volume(mesh)
    if volume is None:
        if topology is not None and topology.passed:
            defects.append("solid volume unavailable")
    elif not math.isfinite(volume) or abs(volume) <= EPSILON:
        defects.append("zero volume")
    elif volume < 0.0 and "inverted normals" not in defects:
        defects.append("inverted normals")

    closed = bool(topology and topology.stats.watertight)
    manifold = bool(
        topology
        and topology.stats.boundary_edges == 0
        and topology.stats.non_manifold_edges == 0
    )
    solid = closed and manifold and volume is not None and volume > EPSILON and not defects
    valid = solid and not defects
    return PartResult(
        id=part_id,
        source_faces=source_faces,
        thicken_dir_mm=thicken_dir_mm,
        solid=solid,
        valid=valid,
        failure_reason=None if valid else "; ".join(dict.fromkeys(defects)),
    )


def _offset_open_triangle_shell(mesh: Any, distance_mm: float) -> Any:
    trimesh, np = _require_trimesh_numpy()
    vertices = np.array(_vertices(mesh), dtype=float)
    faces = np.array(_faces(mesh), dtype=int)
    if len(vertices) == 0 or len(faces) == 0:
        raise ValueError("empty shell")
    if _count_degenerate_faces(tuple(map(tuple, vertices.tolist())), tuple(map(tuple, faces.tolist()))):
        raise ValueError("degenerate face in shell")

    boundary_edges = _directed_boundary_edges(faces)
    if not boundary_edges:
        raise ValueError("open shell has no boundary edges")

    normals = _vertex_normals(vertices, faces, np)
    offset_vertices = vertices + (float(distance_mm) * normals)
    vertex_count = len(vertices)
    solid_vertices = np.vstack((vertices, offset_vertices))

    solid_faces: list[tuple[int, int, int]] = [tuple(map(int, face)) for face in faces]
    solid_faces.extend(
        (int(face[2]) + vertex_count, int(face[1]) + vertex_count, int(face[0]) + vertex_count)
        for face in faces
    )
    for a, b in boundary_edges:
        solid_faces.append((a, b + vertex_count, b))
        solid_faces.append((a + vertex_count, b + vertex_count, a))

    return trimesh.Trimesh(vertices=solid_vertices, faces=np.array(solid_faces, dtype=int), process=False)


def _vertex_normals(vertices: Any, faces: Any, np: Any) -> Any:
    normals = np.zeros_like(vertices, dtype=float)
    for face in faces:
        a, b, c = (int(face[0]), int(face[1]), int(face[2]))
        ab = vertices[b] - vertices[a]
        ac = vertices[c] - vertices[a]
        normal = np.cross(ab, ac)
        length = float(np.linalg.norm(normal))
        if length <= EPSILON:
            raise ValueError("degenerate face in shell")
        normal = normal / length
        normals[a] += normal
        normals[b] += normal
        normals[c] += normal
    lengths = np.linalg.norm(normals, axis=1)
    if bool(np.any(lengths <= EPSILON)):
        raise ValueError("shell has vertices without usable normals")
    return normals / lengths[:, None]


def _directed_boundary_edges(faces: Any) -> list[tuple[int, int]]:
    undirected: list[tuple[int, int]] = []
    directed: list[tuple[int, int]] = []
    for face in faces:
        triplet = (int(face[0]), int(face[1]), int(face[2]))
        for a, b in ((triplet[0], triplet[1]), (triplet[1], triplet[2]), (triplet[2], triplet[0])):
            directed.append((a, b))
            undirected.append(tuple(sorted((a, b))))
    counts = Counter(undirected)
    return [edge for edge in directed if counts[tuple(sorted(edge))] == 1]


def _count_degenerate_faces(
    vertices: Sequence[Sequence[float]],
    faces: Sequence[Sequence[int]],
) -> int:
    count = 0
    for face in faces:
        try:
            ax, ay, az = vertices[int(face[0])]
            bx, by, bz = vertices[int(face[1])]
            cx, cy, cz = vertices[int(face[2])]
        except (IndexError, TypeError, ValueError):
            continue
        ab = (bx - ax, by - ay, bz - az)
        ac = (cx - ax, cy - ay, cz - az)
        cross = (
            (ab[1] * ac[2]) - (ab[2] * ac[1]),
            (ab[2] * ac[0]) - (ab[0] * ac[2]),
            (ab[0] * ac[1]) - (ab[1] * ac[0]),
        )
        area_twice = math.sqrt((cross[0] ** 2) + (cross[1] ** 2) + (cross[2] ** 2))
        if area_twice <= EPSILON:
            count += 1
    return count


def _orientation_candidate(
    name: str,
    *,
    volume: float,
    base_area: float,
    max_face_area: float,
    support_fraction: float,
    show_face_quality: float,
) -> OrientationCandidate:
    support_volume = volume * support_fraction
    stability = 0.0 if max_face_area <= 0 else min(1.0, base_area / max_face_area)
    support_penalty = 0.0 if volume <= 0 else min(60.0, (support_volume / volume) * 100.0)
    score = (stability * 70.0) + (show_face_quality * 30.0) - support_penalty
    return OrientationCandidate(
        name=name,
        support_volume_mm3=_clean(support_volume),
        stability=_clean(stability),
        score=_clean(score),
    )


def _try_place_in_unit(
    pack_unit: dict[str, Any],
    *,
    part_id: str,
    orientations: tuple[tuple[float, float, float], ...],
    unit_width: float,
    unit_depth: float,
) -> dict[str, Any] | None:
    for width, depth, rotation in orientations:
        if width > unit_width + EPSILON or depth > unit_depth + EPSILON:
            continue
        cursor_x = pack_unit["cursor_x"]
        cursor_y = pack_unit["cursor_y"]
        row_height = pack_unit["row_height"]
        if cursor_x + width <= unit_width + EPSILON and cursor_y + depth <= unit_depth + EPSILON:
            return _record_placement(pack_unit, part_id, width, depth, rotation, cursor_x, cursor_y)
        next_y = cursor_y + row_height
        if width <= unit_width + EPSILON and next_y + depth <= unit_depth + EPSILON:
            pack_unit["cursor_x"] = 0.0
            pack_unit["cursor_y"] = next_y
            pack_unit["row_height"] = 0.0
            return _record_placement(pack_unit, part_id, width, depth, rotation, 0.0, next_y)
    return None


def _record_placement(
    pack_unit: dict[str, Any],
    part_id: str,
    width: float,
    depth: float,
    rotation: float,
    x: float,
    y: float,
) -> dict[str, Any]:
    placement = {
        "unit_index": pack_unit["unit_index"],
        "part_id": part_id,
        "x_mm": _clean(x),
        "y_mm": _clean(y),
        "width_mm": _clean(width),
        "depth_mm": _clean(depth),
        "rotation_deg": _clean(rotation),
    }
    pack_unit["placements"].append(placement)
    pack_unit["cursor_x"] = x + width
    pack_unit["row_height"] = max(pack_unit["row_height"], depth)
    pack_unit["max_x"] = max(pack_unit["max_x"], x + width)
    pack_unit["max_y"] = max(pack_unit["max_y"], y + depth)
    return placement


def _centered_layout(pack_unit: dict[str, Any], *, unit_width: float, unit_depth: float) -> list[dict]:
    if not pack_unit["placements"]:
        return []
    offset_x = (unit_width - pack_unit["max_x"]) / 2.0
    offset_y = (unit_depth - pack_unit["max_y"]) / 2.0
    centered: list[dict] = []
    for placement in pack_unit["placements"]:
        row = dict(placement)
        row["x_mm"] = _clean(row["x_mm"] + offset_x)
        row["y_mm"] = _clean(row["y_mm"] + offset_y)
        row["center_x_mm"] = _clean(row["x_mm"] + (row["width_mm"] / 2.0))
        row["center_y_mm"] = _clean(row["y_mm"] + (row["depth_mm"] / 2.0))
        row["plate_width_mm" if unit_width == PRINT_PLATE_MM[0] else "sheet_width_mm"] = _clean(unit_width)
        row["plate_depth_mm" if unit_depth == PRINT_PLATE_MM[1] else "sheet_depth_mm"] = _clean(unit_depth)
        row["centered"] = True
        centered.append(row)
    return centered


def _new_pack_unit(unit_index: int) -> dict[str, Any]:
    return {
        "unit_index": unit_index,
        "placements": [],
        "cursor_x": 0.0,
        "cursor_y": 0.0,
        "row_height": 0.0,
        "max_x": 0.0,
        "max_y": 0.0,
    }


def _packing_orientations(width: float, depth: float) -> tuple[tuple[float, float, float], ...]:
    original = (_clean(width), _clean(depth), 0.0)
    rotated = (_clean(depth), _clean(width), 90.0)
    return (original,) if original[:2] == rotated[:2] else (original, rotated)


def _unit_dimensions_mm(unit: str) -> tuple[str, float, float]:
    normalized = unit.strip().lower()
    if normalized in {"print", "plate", "250x250", "250x250 plate", "250 x 250 plate"}:
        return "250x250 plate", PRINT_PLATE_MM[0], PRINT_PLATE_MM[1]
    if normalized in {"laser", "sheet", "12x12", "12x12 sheet", "12 x 12 sheet"}:
        return "12x12 sheet", LASER_SHEET_MM[0], LASER_SHEET_MM[1]

    match = re.search(r"(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)", normalized)
    if not match:
        raise ValueError(f"unknown fabrication unit: {unit!r}")
    width = float(match.group(1))
    depth = float(match.group(2))
    if "in" in normalized or "inch" in normalized:
        width *= 25.4
        depth *= 25.4
    label = unit.strip()
    return label, width, depth


def _part_is_valid(part: Any) -> bool:
    value = _field(part, "valid", True)
    return bool(value)


def _part_extents_mm(part: Any) -> tuple[float, float, float]:
    mesh = _mesh_from(part)
    if mesh is not None:
        bounds = getattr(mesh, "bounds", None)
        if bounds is None:
            raise ValueError("mesh bounds unavailable")
        return (
            _clean(float(bounds[1][0] - bounds[0][0])),
            _clean(float(bounds[1][1] - bounds[0][1])),
            _clean(float(bounds[1][2] - bounds[0][2])),
        )

    size = _field(part, "size_mm", None)
    if size is None:
        size = _field(part, "extents_mm", None)
    if size is not None and len(size) >= 2:
        height = float(size[2]) if len(size) >= 3 else 0.0
        return _clean(float(size[0])), _clean(float(size[1])), _clean(height)

    bounds_value = _field(part, "bounds", None)
    if bounds_value is not None:
        bounds = list(bounds_value)
        if len(bounds) == 2:
            lower, upper = bounds
            return (
                _clean(float(upper[0]) - float(lower[0])),
                _clean(float(upper[1]) - float(lower[1])),
                _clean(float(upper[2]) - float(lower[2])),
            )
        if len(bounds) == 6:
            return (
                _clean(float(bounds[3]) - float(bounds[0])),
                _clean(float(bounds[4]) - float(bounds[1])),
                _clean(float(bounds[5]) - float(bounds[2])),
            )
    raise ValueError("part dimensions unavailable")


def _mesh_from(item: Any) -> Any | None:
    mesh = _field(item, "mesh", None)
    if mesh is not None:
        return mesh
    if hasattr(item, "vertices") and hasattr(item, "faces"):
        return item
    vertices = _field(item, "vertices", None)
    faces = _field(item, "faces", None)
    if vertices is not None and faces is not None:
        trimesh, np = _require_trimesh_numpy()
        return trimesh.Trimesh(
            vertices=np.array(vertices, dtype=float),
            faces=np.array(faces, dtype=int),
            process=False,
        )
    return None


def _part_id(item: Any, index: int) -> str:
    for name in ("id", "part_id", "name"):
        value = _field(item, name, None)
        if value:
            return str(value)
    metadata = getattr(item, "metadata", None)
    if isinstance(metadata, Mapping):
        for name in ("name", "id", "part_id"):
            value = metadata.get(name)
            if value:
                return str(value)
    mesh = _field(item, "mesh", None)
    metadata = getattr(mesh, "metadata", None)
    if isinstance(metadata, Mapping):
        for name in ("name", "id", "part_id"):
            value = metadata.get(name)
            if value:
                return str(value)
    return f"part_{index + 1}"


def _source_faces(item: Any, mesh: Any | None) -> int:
    source_faces = _field(item, "source_faces", None)
    if source_faces is not None:
        return int(source_faces)
    if mesh is None:
        faces = _field(item, "faces", None)
        return len(faces) if faces is not None else 0
    return len(getattr(mesh, "faces", ()))


def _thicken_dir(item: Any) -> float | None:
    value = _field(item, "thicken_dir_mm", None)
    return None if value is None else float(value)


def _vertices(mesh: Any) -> tuple[tuple[float, float, float], ...]:
    vertices = getattr(mesh, "vertices", ())
    return tuple((float(vertex[0]), float(vertex[1]), float(vertex[2])) for vertex in vertices)


def _faces(mesh: Any) -> tuple[tuple[int, int, int], ...]:
    faces = getattr(mesh, "faces", ())
    return tuple((int(face[0]), int(face[1]), int(face[2])) for face in faces)


def _mesh_volume(mesh: Any) -> float | None:
    vertices = _vertices(mesh)
    faces = _faces(mesh)
    if not vertices or not faces:
        return None
    volume = 0.0
    for face in faces:
        a, b, c = face
        ax, ay, az = vertices[a]
        bx, by, bz = vertices[b]
        cx, cy, cz = vertices[c]
        volume += (
            ax * (by * cz - bz * cy)
            - ay * (bx * cz - bz * cx)
            + az * (bx * cy - by * cx)
        )
    return volume / 6.0


def _component_count(mesh: Any) -> int:
    try:
        components = mesh.split(only_watertight=False)
    except Exception:
        return 1
    return len(components)


def _field(item: Any, name: str, default: Any) -> Any:
    if isinstance(item, Mapping):
        return item.get(name, default)
    return getattr(item, name, default)


def _require_trimesh_numpy() -> tuple[Any, Any]:
    try:
        import numpy as np
        import trimesh
    except ImportError as exc:
        raise RuntimeError("fabrication geometry functions require trimesh and numpy") from exc
    return trimesh, np


def _pluralize(count: int, singular: str) -> str:
    suffix = "" if count == 1 else "s"
    return f"{count} {singular}{suffix}"


def _format_mm(value: float) -> str:
    return f"{_clean(value):g} mm"


def _clean(value: float) -> float:
    if abs(value) <= 1e-12:
        return 0.0
    rounded = round(float(value), 6)
    return int(rounded) if rounded.is_integer() else rounded
