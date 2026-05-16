from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from printpipe.contracts import MeshStats, StageStatus
from printpipe.mesh.repair import MeshRepairError, MeshRepairUnavailableError, repair_mesh_file


TRIMESH_AVAILABLE = importlib.util.find_spec("trimesh") is not None


def test_repair_mesh_file_reports_clear_unavailable_error_without_trimesh(
    tmp_path: Path,
):
    if TRIMESH_AVAILABLE:
        pytest.skip("trimesh is installed; covered by repair smoke test")

    with pytest.raises(MeshRepairUnavailableError, match="trimesh"):
        repair_mesh_file(tmp_path / "input.stl", tmp_path / "output.stl")


@pytest.mark.skipif(not TRIMESH_AVAILABLE, reason="trimesh is not installed")
def test_repair_mesh_file_repairs_and_exports_tiny_mesh(tmp_path: Path):
    import trimesh

    input_path = tmp_path / "input.stl"
    output_path = tmp_path / "output.stl"
    box = trimesh.creation.box(extents=(1.0, 2.0, 3.0))
    mesh = trimesh.Trimesh(
        vertices=box.vertices,
        faces=[*box.faces.tolist(), box.faces[0].tolist()],
        process=False,
    )
    mesh.export(input_path)

    result = repair_mesh_file(input_path, output_path)

    assert result.status is StageStatus.SUCCEEDED
    assert result.output_path == output_path
    assert result.before.faces > result.after.faces
    assert result.after.watertight is True
    assert result.after.boundary_edges == 0
    assert result.after.non_manifold_edges == 0
    assert isinstance(result.before, MeshStats)
    assert isinstance(result.after, MeshStats)
    assert "repaired" in result.message.lower()
    assert output_path.exists()

    repaired = trimesh.load(output_path, force="mesh", process=False)
    assert isinstance(repaired, trimesh.Trimesh)
    assert repaired.is_watertight


@pytest.mark.skipif(not TRIMESH_AVAILABLE, reason="trimesh is not installed")
def test_repair_mesh_file_fails_clearly_when_mesh_stays_non_watertight(
    tmp_path: Path,
):
    import trimesh

    input_path = tmp_path / "open_triangle.stl"
    output_path = tmp_path / "open_triangle_repaired.stl"
    trimesh.Trimesh(
        vertices=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        faces=((0, 1, 2),),
        process=False,
    ).export(input_path)

    with pytest.raises(MeshRepairError, match="non-watertight") as exc_info:
        repair_mesh_file(input_path, output_path)

    assert exc_info.value.result.status is StageStatus.FAILED
    assert exc_info.value.result.after.watertight is False
    assert "non-watertight" in exc_info.value.result.message
