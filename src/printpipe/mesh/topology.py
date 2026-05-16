"""Pure-Python mesh topology helpers.

These helpers operate on triangle index triples instead of concrete mesh
objects so early validation can run without trimesh or numpy installed.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence


Face = tuple[int, int, int]
Edge = tuple[int, int]


def normalize_faces(faces: Iterable[Sequence[int]]) -> tuple[Face, ...]:
    """Return validated triangle index triples."""
    normalized: list[Face] = []
    for face in faces:
        if len(face) != 3:
            raise ValueError(f"mesh faces must be index triples, got {face!r}")
        a, b, c = face
        if not all(isinstance(index, int) for index in (a, b, c)):
            raise TypeError(f"mesh face indices must be integers, got {face!r}")
        if min(a, b, c) < 0:
            raise ValueError(f"mesh face indices must be non-negative, got {face!r}")
        normalized.append((a, b, c))
    return tuple(normalized)


def face_edges(face: Face) -> tuple[Edge, Edge, Edge]:
    """Return sorted undirected edges for one triangular face."""
    a, b, c = face
    return (
        tuple(sorted((a, b))),
        tuple(sorted((b, c))),
        tuple(sorted((c, a))),
    )


def directed_face_edges(face: Face) -> tuple[Edge, Edge, Edge]:
    """Return directed edges for one triangular face."""
    a, b, c = face
    return ((a, b), (b, c), (c, a))


def count_face_edges(faces: Iterable[Sequence[int]]) -> Counter[Edge]:
    """Count sorted undirected edge usage across triangular faces."""
    edge_counts: Counter[Edge] = Counter()
    for face in normalize_faces(faces):
        edge_counts.update(face_edges(face))
    return edge_counts


def infer_vertices_count(faces: Iterable[Face]) -> int:
    """Infer a zero-based vertex count from face indices."""
    max_index: int | None = None
    for face in faces:
        for index in face:
            max_index = index if max_index is None else max(max_index, index)
    return 0 if max_index is None else max_index + 1


def count_boundary_edges(edge_counts: Counter[Edge]) -> int:
    """Count edges used by exactly one face."""
    return sum(1 for count in edge_counts.values() if count == 1)


def count_non_manifold_edges(edge_counts: Counter[Edge]) -> int:
    """Count edges used by more than two faces."""
    return sum(1 for count in edge_counts.values() if count > 2)


def count_inconsistent_winding_edges(faces: Iterable[Sequence[int]]) -> int:
    """Count two-face edges whose adjacent faces use the same edge direction."""
    directed_uses: dict[Edge, list[Edge]] = defaultdict(list)
    for face in normalize_faces(faces):
        for edge in directed_face_edges(face):
            directed_uses[tuple(sorted(edge))].append(edge)

    inconsistent_edges = 0
    for uses in directed_uses.values():
        if len(uses) == 2 and uses[0] == uses[1]:
            inconsistent_edges += 1
    return inconsistent_edges
