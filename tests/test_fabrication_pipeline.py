"""Assembly tests for fabricate(), without requiring trimesh.

Parts are fed as already-built ``PartResult`` objects, so ``thicken_to_solids``
and ``validate`` pass them straight through (a PartResult with no mesh is kept
verbatim). That keeps the whole test on the dependency-light path: orientation
and packing degrade to ``None`` (no extents available) rather than crashing.
"""

from __future__ import annotations

from printpipe.fabrication.pipeline import (
    FabricationModel,
    FabricationSettings,
    FitContext,
    fabricate,
)
from printpipe.fabrication.report import (
    Dimension,
    ExportResult,
    PartResult,
    Provenance,
    Status,
    Target,
)


def _part(part_id: str, *, valid: bool) -> PartResult:
    """A meshless PartResult; validate() passes it through unchanged."""
    return PartResult(
        id=part_id,
        source_faces=100,
        thicken_dir_mm=None,
        solid=valid,
        valid=valid,
        failure_reason=None if valid else "injected invalid solid",
    )


def _fit_context(*, dimensions) -> FitContext:
    return FitContext(
        board_length_mm=114.0,
        board_width_mm=46.0,
        inner_length_mm=116.0,
        inner_width_mm=48.0,
        internal_height_mm=52.0,
        total_height_mm=55.0,
        clearance_mm=1.0,
        standoff_height_mm=12.0,
        boss_height_mm=9.0,
        cutouts=[
            {"face": "-y", "u_mm": -45.5, "z_center_mm": 16.0, "width_mm": 14.0, "height_mm": 12.0},
        ],
        lens={"v_mm": 30.0, "length_mm": 44.0},
        camera={"v_center_mm": 30.0, "post_len_mm": 44.0},
        floor_cutouts=[{"x_mm": 22.0, "y_mm": 0.0, "size_x_mm": 20.0, "size_y_mm": 18.0}],
        bracket_footprint_mm=(16.0, 14.0),
        mount_holes_xy=[(4.0, 11.5), (4.0, -11.5), (-54.0, 11.5), (-54.0, -11.5)],
        grip={"mount_span_mm": 110.0, "mount_hole_dia_mm": 4.0},
        body_grip_holes={"u_positions": [-55.0, 55.0], "diameter_mm": 3.4},
        dimensions=dimensions,
    )


def test_fabricate_assembles_report():
    dimensions = [Dimension("inner_length_mm", 116.0, Provenance.MEASURED)]
    model = FabricationModel(
        parts=[_part("body", valid=True), _part("lid", valid=True)],
        fit=_fit_context(dimensions=dimensions),
        dimensions=dimensions,
    )
    report = fabricate(model, Target.PRINT, FabricationSettings())

    assert report.units == "mm"
    assert report.target == Target.PRINT
    assert report.valid_solids == "2 / 2"
    # printability is produced by check_fit (7 checks for this product).
    assert len(report.printability) == 7
    assert isinstance(report.exports, ExportResult)
    assert report.exports.stl_paths == []  # empty stub
    assert isinstance(report.agent_summary, str) and report.agent_summary
    assert "Valid solids: 2 / 2" in report.agent_summary


def test_positional_target_overrides_settings():
    dimensions = [Dimension("inner_length_mm", 116.0, Provenance.MEASURED)]
    model = FabricationModel(
        parts=[_part("body", valid=True)],
        fit=None,
        dimensions=dimensions,
    )
    # Settings say PRINT, positional arg says LASER; positional must win.
    report = fabricate(model, Target.LASER, FabricationSettings(target=Target.PRINT))
    assert report.target == Target.LASER
    assert report.printability == []  # no fit context


def test_ready_to_print_blocked_by_injected_fail():
    # A board larger than the shell makes check (1) FAIL -> not ready to print.
    fit = _fit_context(dimensions=[Dimension("inner_length_mm", 116.0, Provenance.MEASURED)])
    fit = FitContext(**{**fit.__dict__, "board_length_mm": 130.0})
    model = FabricationModel(
        parts=[_part("body", valid=True)],
        fit=fit,
        dimensions=[Dimension("inner_length_mm", 116.0, Provenance.MEASURED)],
    )
    report = fabricate(model, Target.PRINT, FabricationSettings())

    assert any(c.status == Status.FAIL for c in report.printability)
    assert report.ready_to_print is False


def test_ready_to_print_blocked_by_assumed_fit_critical_dim():
    # All checks pass and all parts valid, but an assumed + fit_critical
    # dimension blocks ready_to_print per the report contract.
    dimensions = [Dimension("inner_length_mm", 116.0, Provenance.ASSUMED, fit_critical=True)]
    model = FabricationModel(
        parts=[_part("body", valid=True)],
        fit=_fit_context(dimensions=dimensions),
        dimensions=dimensions,
    )
    report = fabricate(model, Target.PRINT, FabricationSettings())

    assert report.ready_to_print is False
    assert "inner_length_mm" in report.agent_summary


def test_ready_to_print_blocked_by_invalid_part():
    dimensions = [Dimension("inner_length_mm", 116.0, Provenance.MEASURED)]
    model = FabricationModel(
        parts=[_part("body", valid=True), _part("lid", valid=False)],
        fit=_fit_context(dimensions=dimensions),
        dimensions=dimensions,
    )
    report = fabricate(model, Target.PRINT, FabricationSettings())

    assert report.valid_solids == "1 / 2"
    assert report.ready_to_print is False


def test_agent_summary_lists_non_pass_checks():
    fit = _fit_context(dimensions=[Dimension("inner_length_mm", 116.0, Provenance.MEASURED)])
    fit = FitContext(**{**fit.__dict__, "board_length_mm": 130.0})
    model = FabricationModel(
        parts=[_part("body", valid=True)],
        fit=fit,
        dimensions=[Dimension("inner_length_mm", 116.0, Provenance.MEASURED)],
    )
    report = fabricate(model, Target.PRINT, FabricationSettings())
    assert "Fit issues:" in report.agent_summary
    assert "[fail]" in report.agent_summary
