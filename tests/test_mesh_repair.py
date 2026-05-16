from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from printpipe.contracts import ArtifactKind, MeshStats, StageStatus
from printpipe.mesh import repair
from printpipe.mesh.repair import (
    MeshRepairError,
    MeshRepairResult,
    MeshRepairUnavailableError,
    repair_mesh_file,
)


TRIMESH_AVAILABLE = importlib.util.find_spec("trimesh") is not None


def test_repair_mesh_file_reports_clear_unavailable_error_without_trimesh(
    tmp_path: Path,
):
    if TRIMESH_AVAILABLE:
        pytest.skip("trimesh is installed; covered by repair smoke test")

    with pytest.raises(MeshRepairUnavailableError, match="trimesh"):
        repair_mesh_file(tmp_path / "input.stl", tmp_path / "output.stl")


def test_repair_mesh_file_to_receipt_records_unavailable_dependency(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    def raise_unavailable():
        raise MeshRepairUnavailableError("trimesh unavailable for test")

    monkeypatch.setattr(repair, "_import_trimesh", raise_unavailable)

    receipt = repair.repair_mesh_file_to_receipt(
        tmp_path / "input.stl",
        tmp_path / "output.stl",
        stats_path=tmp_path / "repair_stats.json",
    )

    assert receipt.stage == "mesh_repair"
    assert receipt.status is StageStatus.SKIPPED
    assert "trimesh" in receipt.message
    assert len(receipt.artifacts) == 1
    assert receipt.artifacts[0].kind is ArtifactKind.REPORT
    assert receipt.artifacts[0].path == tmp_path / "repair_stats.json"
    assert receipt.metrics["dependency"] == "trimesh"

    stats = json.loads((tmp_path / "repair_stats.json").read_text())
    assert stats["status"] == StageStatus.SKIPPED.value
    assert stats["dependency"] == "trimesh"
    assert stats["input_path"].endswith("input.stl")
    assert stats["output_path"].endswith("output.stl")


def test_repair_mesh_file_to_receipt_writes_success_receipt_without_real_trimesh(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    def fake_repair_mesh_file(
        input_path: Path | str,
        output_path: Path | str,
        *,
        allow_non_watertight: bool = False,
    ) -> MeshRepairResult:
        del input_path, allow_non_watertight
        output = Path(output_path)
        output.write_text("solid repaired\nendsolid repaired\n")
        return MeshRepairResult(
            before=MeshStats(vertices=4, faces=2, watertight=False, boundary_edges=4),
            after=MeshStats(vertices=4, faces=4, watertight=True, boundary_edges=0),
            output_path=output,
            status=StageStatus.SUCCEEDED,
            message="Repaired mesh written to output.stl.",
        )

    monkeypatch.setattr(repair, "repair_mesh_file", fake_repair_mesh_file)

    output_path = tmp_path / "output.stl"
    stats_path = tmp_path / "repair_stats.json"
    receipt = repair.repair_mesh_file_to_receipt(
        tmp_path / "input.stl",
        output_path,
        stats_path=stats_path,
    )

    assert receipt.status is StageStatus.SUCCEEDED
    assert [artifact.kind for artifact in receipt.artifacts] == [
        ArtifactKind.REPAIRED_MESH,
        ArtifactKind.REPORT,
    ]
    assert receipt.artifacts[0].path == output_path
    assert receipt.artifacts[1].path == stats_path
    assert receipt.metrics["watertight_before"] is False
    assert receipt.metrics["watertight_after"] is True

    stats = json.loads(stats_path.read_text())
    assert stats["stage"] == "mesh_repair"
    assert stats["status"] == StageStatus.SUCCEEDED.value
    assert stats["before"]["boundary_edges"] == 4
    assert stats["after"]["boundary_edges"] == 0


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

    repaired = trimesh.load(output_path, force="mesh", process=True)
    assert isinstance(repaired, trimesh.Trimesh)
    assert repaired.is_watertight


@pytest.mark.skipif(not TRIMESH_AVAILABLE, reason="trimesh is not installed")
def test_repair_mesh_file_to_receipt_writes_stats_and_artifacts(tmp_path: Path):
    import trimesh

    input_path = tmp_path / "input.stl"
    output_path = tmp_path / "output.stl"
    stats_path = tmp_path / "repair_stats.json"
    mesh = trimesh.creation.box(extents=(1.0, 2.0, 3.0))
    mesh.export(input_path)

    receipt = repair.repair_mesh_file_to_receipt(
        input_path,
        output_path,
        stats_path=stats_path,
    )

    assert receipt.stage == "mesh_repair"
    assert receipt.status is StageStatus.SUCCEEDED
    assert receipt.artifacts[0].kind is ArtifactKind.REPAIRED_MESH
    assert receipt.artifacts[0].path == output_path
    assert receipt.artifacts[1].kind is ArtifactKind.REPORT
    assert receipt.artifacts[1].path == stats_path
    assert receipt.metrics["watertight_after"] is True
    assert output_path.exists()

    stats = json.loads(stats_path.read_text())
    assert stats["status"] == StageStatus.SUCCEEDED.value
    assert stats["before"]["watertight"] is False
    assert stats["after"]["watertight"] is True
    assert stats["output_path"] == str(output_path)


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
