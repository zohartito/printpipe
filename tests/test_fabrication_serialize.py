from __future__ import annotations

import json

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
from printpipe.fabrication.serialize import (
    FABRICATION_REPORT_SCHEMA_VERSION,
    to_dict,
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
        dimensions=dimensions
        or [Dimension("lens_length", 45.0, Provenance.DATASHEET, source="spec sheet")],
        parts=parts or [PartResult("body", 12, None, solid=True, valid=True)],
        valid_solids="1 / 1",
        printability=printability
        or [Check("clearance", Status.PASS, "lens clears the faceplate")],
        orientation=None,
        packing=packing
        or PackingResult(
            "250x250 plate",
            1,
            [{"part_id": "body", "x_mm": 10.0, "y_mm": 10.0, "centered": True}],
            0.42,
        ),
        exports=ExportResult(openable_3mf="runs/body.3mf", stl_paths=["runs/body.stl"]),
        agent_summary="ready",
    )


def test_to_dict_is_json_round_trippable() -> None:
    serialized = to_dict(_report())

    assert json.loads(json.dumps(serialized)) == serialized


def test_to_dict_emits_enum_values_as_lowercase_strings() -> None:
    serialized = to_dict(_report())

    assert serialized["target"] == "print"
    assert serialized["dimensions"][0]["provenance"] == "datasheet"
    assert serialized["printability"][0]["status"] == "pass"


def test_to_dict_emits_schema_version() -> None:
    serialized = to_dict(_report())

    assert serialized["schema_version"] == 1
    assert serialized["schema_version"] == FABRICATION_REPORT_SCHEMA_VERSION


def test_to_dict_preserves_nested_lists() -> None:
    serialized = to_dict(_report())

    assert isinstance(serialized["parts"], list) and serialized["parts"]
    assert isinstance(serialized["printability"], list) and serialized["printability"]
    assert isinstance(serialized["dimensions"], list) and serialized["dimensions"]


def test_to_dict_reports_ready_to_print_true_for_all_clear_report() -> None:
    serialized = to_dict(_report())

    assert serialized["ready_to_print"] is True


def test_to_dict_reports_ready_to_print_false_for_assumed_fit_critical_dim() -> None:
    assumed = Dimension(
        "lens_length",
        45.0,
        Provenance.ASSUMED,
        fit_critical=True,
        source="recipe default",
    )

    serialized = to_dict(_report(dimensions=[assumed]))

    assert serialized["ready_to_print"] is False


def test_to_dict_collapses_absent_optionals_to_none() -> None:
    report = _report()
    report.orientation = None

    serialized = to_dict(report)

    assert serialized["orientation"] is None
    assert serialized["parts"][0]["thicken_dir_mm"] is None
    assert serialized["parts"][0]["failure_reason"] is None
