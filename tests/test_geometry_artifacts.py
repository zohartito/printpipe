from __future__ import annotations

import json
import math

from printpipe.contracts import ArtifactKind, StageStatus
from printpipe.geometry import (
    compute_bounds,
    read_ascii_stl_vertices,
    write_oriented_ascii_stl_artifacts,
)


def write_fixture_stl(path):
    path.write_text(
        "\n".join(
            (
                "solid offset_box",
                "  facet normal 0 0 1",
                "    outer loop",
                "      vertex 10 20 5",
                "      vertex 30 20 5",
                "      vertex 30 30 5",
                "    endloop",
                "  endfacet",
                "  facet normal 0 0 1",
                "    outer loop",
                "      vertex 10 20 15",
                "      vertex 30 20 15",
                "      vertex 30 30 15",
                "    endloop",
                "  endfacet",
                "endsolid offset_box",
                "",
            )
        ),
        encoding="utf-8",
    )


def test_write_oriented_ascii_stl_creates_mesh_and_json_sidecar(tmp_path):
    input_path = tmp_path / "source.stl"
    write_fixture_stl(input_path)

    receipt = write_oriented_ascii_stl_artifacts(input_path, tmp_path / "oriented")

    assert receipt.status is StageStatus.SUCCEEDED
    assert receipt.stage == "geometry.write_oriented_ascii_stl_artifacts"
    assert receipt.metrics["triangle_count"] == 2
    assert receipt.metrics["vertex_count"] == 6
    assert {artifact.kind for artifact in receipt.artifacts} == {
        ArtifactKind.ORIENTED_MESH,
        ArtifactKind.REPORT,
    }

    mesh_path = tmp_path / "oriented" / "source_oriented.stl"
    json_path = tmp_path / "oriented" / "source_orientation.json"
    assert mesh_path.exists()
    assert json_path.exists()
    assert mesh_path.read_text(encoding="utf-8").startswith("solid source_oriented")


def test_write_oriented_ascii_stl_drops_z_and_centers_xy_bounds(tmp_path):
    input_path = tmp_path / "source.stl"
    write_fixture_stl(input_path)

    write_oriented_ascii_stl_artifacts(input_path, tmp_path / "oriented")

    vertices = read_ascii_stl_vertices(tmp_path / "oriented" / "source_oriented.stl")
    bounds = compute_bounds(vertices)
    assert bounds.min_z == 0.0
    assert bounds.center_x == 0.0
    assert bounds.center_y == 0.0
    assert bounds.width_x == 20.0
    assert bounds.depth_y == 10.0
    assert bounds.height_z == 10.0


def test_write_oriented_ascii_stl_records_rotation_and_scale_metrics(tmp_path):
    input_path = tmp_path / "source.stl"
    write_fixture_stl(input_path)

    receipt = write_oriented_ascii_stl_artifacts(
        input_path,
        tmp_path / "oriented",
        scale_factor=2.0,
        rotation_degrees=90.0,
    )

    assert receipt.metrics["scale_factor"] == 2.0
    assert receipt.metrics["rotation_degrees"] == 90.0
    assert receipt.metrics["transform_order"] == "scale_then_rotate_z_then_center_xy_drop_z"
    assert receipt.metrics["source_bounds_mm"]["width_x"] == 20.0
    assert receipt.metrics["oriented_bounds_mm"]["height_z"] == 20.0

    vertices = read_ascii_stl_vertices(tmp_path / "oriented" / "source_oriented.stl")
    bounds = compute_bounds(vertices)
    assert math.isclose(bounds.width_x, 20.0)
    assert math.isclose(bounds.depth_y, 40.0)
    assert math.isclose(bounds.height_z, 20.0)


def test_write_oriented_ascii_stl_json_sidecar_matches_receipt(tmp_path):
    input_path = tmp_path / "source.stl"
    write_fixture_stl(input_path)

    receipt = write_oriented_ascii_stl_artifacts(
        input_path,
        tmp_path / "oriented",
        scale_factor=1.5,
        rotation_degrees=45.0,
        stem="custom_part",
    )

    sidecar = json.loads((tmp_path / "oriented" / "custom_part_orientation.json").read_text())
    assert sidecar["input_path"] == str(input_path)
    assert sidecar["output_mesh_path"].endswith("custom_part.stl")
    assert sidecar["metrics"] == receipt.metrics
    assert sidecar["artifacts"][0]["kind"] == "oriented_mesh"
    assert sidecar["heuristics"]["semantic_claim"] is False


def test_write_oriented_ascii_stl_fails_clearly_for_unsupported_input(tmp_path):
    input_path = tmp_path / "mesh.glb"
    input_path.write_bytes(b"glTF binary placeholder")

    receipt = write_oriented_ascii_stl_artifacts(input_path, tmp_path / "oriented")

    assert receipt.status is StageStatus.FAILED
    assert receipt.artifacts == ()
    assert "only ASCII .stl inputs are supported" in receipt.message

