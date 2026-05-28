"""Mesh pipeline adapters for Bambu-native 3MF bundle writing."""

from __future__ import annotations

import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .core import BambuProfileIds, GuiSafeTransform, MeshGeometry, write_bundle

Vertex = tuple[float, float, float]
Triangle = tuple[int, int, int]


def read_ascii_stl(path: str | Path) -> MeshGeometry:
    """Read a simple triangular ASCII STL fixture into `MeshGeometry`.

    This is intentionally small and strict. It supports the common fixture
    shape made of `facet normal`, `outer loop`, three `vertex` lines,
    `endloop`, and `endfacet`. Binary STL and richer mesh formats are left to
    later pipeline adapters.
    """

    stl_path = Path(path)
    raw = stl_path.read_bytes()
    if not raw:
        raise ValueError(f"ASCII STL file is empty: {stl_path}")
    if b"\0" in raw:
        raise ValueError("binary STL is not supported; expected ASCII STL text")

    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValueError("binary STL is not supported; expected ASCII STL text") from exc

    lines = [
        (line_number, line.strip())
        for line_number, line in enumerate(text.splitlines(), start=1)
        if line.strip()
    ]
    if not lines:
        raise ValueError(f"ASCII STL file is empty: {stl_path}")

    first_line = lines[0][1].split(maxsplit=1)[0].lower()
    if first_line != "solid":
        raise ValueError("only ASCII STL files beginning with 'solid' are supported")

    facets: list[tuple[Vertex, Vertex, Vertex]] = []
    index = 1
    saw_end = False
    while index < len(lines):
        line_number, line = lines[index]
        tokens = line.split()
        keyword = tokens[0].lower()

        if keyword == "endsolid":
            saw_end = True
            if index != len(lines) - 1:
                extra_line_number = lines[index + 1][0]
                raise ValueError(f"line {extra_line_number}: unexpected content after endsolid")
            break

        if keyword != "facet":
            raise ValueError(f"line {line_number}: expected 'facet normal' or 'endsolid'")
        index, facet = _read_facet(lines, index)
        facets.append(facet)

    if not saw_end:
        raise ValueError("ASCII STL must end with 'endsolid'")
    if not facets:
        raise ValueError("ASCII STL must contain at least one triangular facet")

    vertices: list[Vertex] = []
    triangles: list[Triangle] = []
    vertex_indices: dict[Vertex, int] = {}
    for facet in facets:
        triangle_indices: list[int] = []
        for vertex in facet:
            if vertex not in vertex_indices:
                vertex_indices[vertex] = len(vertices)
                vertices.append(vertex)
            triangle_indices.append(vertex_indices[vertex])
        triangles.append((triangle_indices[0], triangle_indices[1], triangle_indices[2]))

    return MeshGeometry(vertices=tuple(vertices), triangles=tuple(triangles))


def write_bundle_from_ascii_stl(
    stl_path: str | Path,
    bundle_path: str | Path,
    profile_ids: BambuProfileIds,
    object_name: str = "printpipe_object",
    transform: GuiSafeTransform | None = None,
    filament_settings: Mapping[str, Any] | None = None,
    process_settings: Mapping[str, Any] | None = None,
    printer_settings: Mapping[str, Any] | None = None,
) -> Path:
    """Convert an ASCII STL to `MeshGeometry`, then write a Bambu 3MF bundle."""

    mesh = read_ascii_stl(stl_path)
    return write_bundle(
        bundle_path,
        mesh=mesh,
        profile_ids=profile_ids,
        object_name=object_name,
        transform=transform,
        filament_settings=filament_settings,
        process_settings=process_settings,
        printer_settings=printer_settings,
    )


def _read_facet(
    lines: list[tuple[int, str]],
    start_index: int,
) -> tuple[int, tuple[Vertex, Vertex, Vertex]]:
    line_number, line = lines[start_index]
    tokens = line.split()
    if len(tokens) != 5 or tokens[1].lower() != "normal":
        raise ValueError(f"line {line_number}: expected 'facet normal nx ny nz'")
    _parse_float_triplet(tokens[2:], line_number, "facet normal")

    outer_index = start_index + 1
    _expect_line(lines, outer_index, ("outer", "loop"))

    vertices: list[Vertex] = []
    index = outer_index + 1
    while index < len(lines):
        current_line_number, current_line = lines[index]
        current_tokens = current_line.split()
        current_keyword = current_tokens[0].lower()
        if current_keyword == "endloop":
            break
        if current_keyword != "vertex":
            raise ValueError(f"line {current_line_number}: expected 'vertex' or 'endloop'")
        if len(current_tokens) != 4:
            raise ValueError(f"line {current_line_number}: expected 'vertex x y z'")
        vertices.append(_parse_float_triplet(current_tokens[1:], current_line_number, "vertex"))
        index += 1

    if index >= len(lines):
        raise ValueError(f"line {line_number}: facet is missing endloop")
    if len(vertices) != 3:
        raise ValueError(
            f"line {line_number}: facet must contain exactly 3 vertices; found {len(vertices)}"
        )

    _expect_line(lines, index, ("endloop",))
    endfacet_index = index + 1
    _expect_line(lines, endfacet_index, ("endfacet",))

    return endfacet_index + 1, (vertices[0], vertices[1], vertices[2])


def _expect_line(lines: list[tuple[int, str]], index: int, expected_tokens: tuple[str, ...]) -> None:
    if index >= len(lines):
        expected = " ".join(expected_tokens)
        raise ValueError(f"expected '{expected}' before end of file")

    line_number, line = lines[index]
    tokens = tuple(token.lower() for token in line.split())
    if tokens != expected_tokens:
        expected = " ".join(expected_tokens)
        raise ValueError(f"line {line_number}: expected '{expected}'")


def _parse_float_triplet(tokens: list[str], line_number: int, label: str) -> Vertex:
    if len(tokens) != 3:
        raise ValueError(f"line {line_number}: expected 3 numbers for {label}")

    try:
        x, y, z = (float(token) for token in tokens)
    except ValueError as exc:
        raise ValueError(f"line {line_number}: {label} contains a non-numeric value") from exc

    if not (math.isfinite(x) and math.isfinite(y) and math.isfinite(z)):
        raise ValueError(f"line {line_number}: {label} values must be finite")
    return (x, y, z)


__all__ = ["read_ascii_stl", "write_bundle_from_ascii_stl"]
