from __future__ import annotations

import json
from pathlib import Path

import pytest

from printpipe.mesh.validate import (
    MeshValidationError,
    gate_mesh_topology,
    validate_mesh_topology,
)


TETRAHEDRON_FACES = (
    (0, 1, 2),
    (0, 3, 1),
    (1, 3, 2),
    (2, 3, 0),
)


def test_validate_mesh_topology_accepts_watertight_tetrahedron():
    result = validate_mesh_topology(TETRAHEDRON_FACES, vertices_count=4)

    assert result.passed is True
    assert result.stats.vertices == 4
    assert result.stats.faces == 4
    assert result.stats.watertight is True
    assert result.stats.euler_number == 2
    assert result.stats.boundary_edges == 0
    assert result.stats.non_manifold_edges == 0
    assert result.defects == ()


def test_gate_mesh_topology_writes_json_for_passing_mesh(tmp_path: Path):
    stats_path = tmp_path / "mesh_stats.json"

    result = gate_mesh_topology(
        TETRAHEDRON_FACES,
        vertices_count=4,
        stats_path=stats_path,
    )

    payload = json.loads(stats_path.read_text())
    assert result.passed is True
    assert payload["passed"] is True
    assert payload["stats"]["vertices"] == 4
    assert payload["stats"]["faces"] == 4
    assert payload["stats"]["watertight"] is True
    assert payload["stats"]["boundary_edges"] == 0
    assert payload["stats"]["non_manifold_edges"] == 0
    assert payload["defects"] == []


def test_gate_mesh_topology_fails_clearly_and_writes_json_for_open_triangle(
    tmp_path: Path,
):
    stats_path = tmp_path / "mesh_stats.json"

    with pytest.raises(MeshValidationError, match="3 boundary edge"):
        gate_mesh_topology(
            ((0, 1, 2),),
            vertices_count=3,
            stats_path=stats_path,
        )

    payload = json.loads(stats_path.read_text())
    assert payload["passed"] is False
    assert payload["stats"]["vertices"] == 3
    assert payload["stats"]["faces"] == 1
    assert payload["stats"]["watertight"] is False
    assert payload["stats"]["boundary_edges"] == 3
    assert payload["stats"]["non_manifold_edges"] == 0
    assert payload["defects"] == ["3 boundary edges"]


def test_validate_mesh_topology_counts_non_manifold_edges():
    result = validate_mesh_topology(
        (
            (0, 1, 2),
            (1, 0, 3),
            (0, 1, 4),
        ),
        vertices_count=5,
    )

    assert result.passed is False
    assert result.stats.boundary_edges == 6
    assert result.stats.non_manifold_edges == 1
    assert "1 non-manifold edge" in result.defects


def test_validate_mesh_topology_detects_inconsistent_face_winding():
    result = validate_mesh_topology(
        (
            (2, 1, 0),
            (0, 3, 1),
            (1, 3, 2),
            (2, 3, 0),
        ),
        vertices_count=4,
    )

    assert result.passed is False
    assert result.stats.watertight is True
    assert result.diagnostics["inconsistent_winding_edges"] == 3
    assert "3 inconsistent winding edges" in result.defects
