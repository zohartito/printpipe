from __future__ import annotations

import math

import pytest

pytest.importorskip("trimesh")  # fabrication verification needs the optional trimesh dependency

import trimesh

from printpipe.fabrication.report import (
    Check,
    Dimension,
    ExportResult,
    FabricationReport,
    PackingResult,
    PartResult,
    Provenance,
    Status,
    Target,
)
from printpipe.fabrication.verification import (
    pack,
    score_orientations,
    thicken_to_solids,
    validate,
)


def _report(
    *,
    dimensions: list[Dimension] | None = None,
    parts: list[PartResult] | None = None,
    printability: list[Check] | None = None,
    packing: PackingResult | None = None,
) -> FabricationReport:
    return FabricationReport(
        units="mm",
        tolerance_mm=0.01,
        wall_thickness_mm=1.2,
        target=Target.PRINT,
        dimensions=dimensions or [],
        parts=parts or [PartResult("body", 12, None, solid=True, valid=True)],
        valid_solids="1 / 1",
        printability=printability or [],
        orientation=None,
        packing=packing,
        exports=ExportResult(openable_3mf="runs/body.3mf"),
        agent_summary="ready",
    )


def _open_square(*, reversed_winding: bool = False) -> trimesh.Trimesh:
    faces = ((0, 2, 1), (0, 3, 2)) if reversed_winding else ((0, 1, 2), (0, 2, 3))
    return trimesh.Trimesh(
        vertices=((0, 0, 0), (20, 0, 0), (20, 20, 0), (0, 20, 0)),
        faces=faces,
        process=False,
        metadata={"name": "return_panel"},
    )


def _part_size(part_id: str, width: float, depth: float, *, valid: bool = True) -> dict[str, object]:
    return {"id": part_id, "size_mm": (width, depth, 3.0), "valid": valid}


def test_fabrication_report_ready_to_print_blocks_failed_inputs() -> None:
    assert _report().ready_to_print is True

    assumed = Dimension(
        "lens_length",
        45.0,
        Provenance.ASSUMED,
        fit_critical=True,
        source="recipe default",
    )
    assert _report(dimensions=[assumed]).ready_to_print is False

    failed_check = Check("clearance", Status.FAIL, "lens collides with faceplate")
    assert _report(printability=[failed_check]).ready_to_print is False

    invalid_part = PartResult("return_06", 8, None, solid=False, valid=False, failure_reason="open mesh")
    assert _report(parts=[invalid_part]).ready_to_print is False

    unplaced = PackingResult("250x250 plate", 1, [], 0.0, unplaced=["return_06"])
    assert _report(packing=unplaced).ready_to_print is False


def test_validate_accepts_closed_solid_and_counts_valid_parts() -> None:
    mesh = trimesh.creation.box(extents=(10, 12, 4))
    mesh.metadata["name"] = "solid_box"

    result = validate([mesh])

    assert len(result) == 1
    assert result[0] == PartResult(
        id="solid_box",
        source_faces=12,
        thicken_dir_mm=None,
        solid=True,
        valid=True,
        failure_reason=None,
    )
    assert sum(part.valid for part in result) == 1


def test_validate_reports_open_non_manifold_inverted_and_degenerate_reasons() -> None:
    open_mesh = _open_square()
    open_mesh.metadata["name"] = "open_panel"
    non_manifold = trimesh.Trimesh(
        vertices=((0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1), (0, 0, -1)),
        faces=((0, 1, 2), (1, 0, 3), (0, 1, 4)),
        process=False,
        metadata={"name": "non_manifold"},
    )
    inverted = trimesh.creation.box(extents=(4, 4, 4))
    inverted.invert()
    inverted.metadata["name"] = "inverted_box"
    degenerate = trimesh.Trimesh(
        vertices=((0, 0, 0), (1, 0, 0), (2, 0, 0)),
        faces=((0, 1, 2),),
        process=False,
        metadata={"name": "flat_line"},
    )

    by_id = {part.id: part for part in validate([open_mesh, non_manifold, inverted, degenerate])}

    assert by_id["open_panel"].valid is False
    assert "boundary edge" in by_id["open_panel"].failure_reason
    assert by_id["non_manifold"].valid is False
    assert "non-manifold edge" in by_id["non_manifold"].failure_reason
    assert by_id["inverted_box"].valid is False
    assert "inverted normals" in by_id["inverted_box"].failure_reason
    assert by_id["flat_line"].valid is False
    assert "degenerate face" in by_id["flat_line"].failure_reason


def test_thicken_to_solids_retries_opposite_direction_when_first_offset_flips() -> None:
    result = thicken_to_solids([_open_square()], wall_mm=0.66)

    assert len(result) == 1
    assert result[0].id == "return_panel"
    assert result[0].valid is True
    assert result[0].solid is True
    assert result[0].thicken_dir_mm == -0.66


def test_thicken_to_solids_leaves_existing_solids_unthickened() -> None:
    solid = trimesh.creation.box(extents=(10, 12, 4))
    solid.metadata["name"] = "solid_box"

    result = thicken_to_solids([solid], wall_mm=1.2)

    assert result[0].valid is True
    assert result[0].solid is True
    assert result[0].thicken_dir_mm is None


def test_thicken_to_solids_flags_unthickenable_degenerate_shells() -> None:
    degenerate = trimesh.Trimesh(
        vertices=((0, 0, 0), (1, 0, 0), (2, 0, 0)),
        faces=((0, 1, 2),),
        process=False,
        metadata={"name": "bad_return"},
    )

    result = thicken_to_solids([degenerate], wall_mm=0.66)

    assert result[0].id == "bad_return"
    assert result[0].valid is False
    assert result[0].solid is False
    assert result[0].thicken_dir_mm is None
    assert "un-thickenable" in result[0].failure_reason


def test_thicken_to_solids_rejects_non_positive_wall_thickness() -> None:
    with pytest.raises(ValueError, match="wall_mm must be positive"):
        thicken_to_solids([_open_square()], wall_mm=0)


def test_score_orientations_prefers_flat_outer_face_for_low_support_stable_panel() -> None:
    mesh = trimesh.creation.box(extents=(80, 40, 4))

    candidates = score_orientations(mesh)

    assert [candidate.name for candidate in candidates] == [
        "flat_outer_face",
        "upright_edge_on_bed",
    ]
    assert candidates[0].support_volume_mm3 < candidates[1].support_volume_mm3
    assert candidates[0].stability > candidates[1].stability
    assert candidates[0].score > candidates[1].score


def test_pack_places_valid_parts_on_centered_250mm_print_plates() -> None:
    result = pack(
        [
            _part_size("a", 90, 70),
            _part_size("b", 80, 70),
            _part_size("c", 130, 130),
        ],
        unit="print",
    )

    assert result.unit == "250x250 plate"
    assert result.units_used == 1
    assert result.unplaced == []
    assert result.efficiency == pytest.approx(((90 * 70) + (80 * 70) + (130 * 130)) / (250 * 250))
    assert [item["part_id"] for item in result.layout] == ["a", "b", "c"]
    assert min(item["x_mm"] for item in result.layout) > 0
    assert min(item["y_mm"] for item in result.layout) > 0
    assert all(item["centered"] is True for item in result.layout)


def test_pack_spills_to_multiple_units_and_reports_unplaced_parts() -> None:
    result = pack(
        [
            _part_size("plate_1", 130, 130),
            _part_size("plate_2", 130, 130),
            _part_size("too_big", 260, 10),
            _part_size("invalid", 10, 10, valid=False),
        ],
        unit="250x250 plate",
    )

    assert result.units_used == 2
    assert {item["unit_index"] for item in result.layout} == {1, 2}
    assert result.unplaced == ["too_big", "invalid"]


def test_pack_laser_uses_twelve_inch_sheet_dimensions_in_mm() -> None:
    result = pack([_part_size("panel", 300, 100)], unit="laser")

    assert result.unit == "12x12 sheet"
    assert result.units_used == 1
    assert result.layout[0]["width_mm"] == 300
    assert result.layout[0]["sheet_width_mm"] == 304.8
    assert math.isclose(result.efficiency, 30000 / (304.8 * 304.8))
