"""Tests for the Phase-0 run -> FabricationReport bridge."""

from __future__ import annotations

from printpipe.fabrication import runs as fab_runs
from printpipe.fabrication.report import Status
from printpipe.fabrication.serialize import to_dict


def _detail(
    *,
    manifold_state="pass",
    slice_state="pass",
    run_id="run_abc",
    warnings=None,
    artifacts=None,
):
    """A representative build_run_detail() output with tunable check states."""
    return {
        "schema_version": 1,
        "run_id": run_id,
        "run_root": "/runs/run_abc",
        "geometry": {"bounds_mm": [10.0, 20.0, 30.0]},
        "print_verdict": {
            "state": "ready",
            "label": "Ready to print",
            "reason": "All available validation checks passed.",
        },
        "validation": [
            {
                "key": "manifold",
                "label": "Manifold / watertight",
                "state": manifold_state,
                "detail": "Mesh repair reports a closed printable shell."
                if manifold_state == "pass"
                else "Mesh still has open or non-manifold geometry.",
            },
            {"key": "bed_fit", "label": "Bed fit", "state": "pass", "detail": "Fits the plate."},
            {
                "key": "material_profile",
                "label": "Material / profile",
                "state": "pass",
                "detail": "Bambu PLA Basic / 0.20mm",
            },
            {"key": "support_risk", "label": "Support risk", "state": "pass", "detail": "Low support risk."},
            {
                "key": "slice_success",
                "label": "Slice success",
                "state": slice_state,
                "detail": "Slice gate completed successfully."
                if slice_state == "pass"
                else "Slice gate failed; inspect slicer logs.",
            },
        ],
        "warnings": warnings or [],
        "artifacts": artifacts or {},
    }


def _patch_detail(monkeypatch, detail):
    monkeypatch.setattr(fab_runs, "build_run_detail", lambda run_root: detail)


def test_passing_run_maps_to_valid_part_and_ready(monkeypatch):
    _patch_detail(monkeypatch, _detail())
    report = fab_runs.build_fabrication_report("/runs/run_abc")

    assert len(report.parts) == 1
    part = report.parts[0]
    assert part.id == "run_abc"
    assert part.valid is True
    assert part.solid is True
    assert part.failure_reason is None
    assert part.source_faces == 0  # legacy runs carry no triangle count

    assert report.units == "mm"
    assert report.tolerance_mm == 0.01
    assert report.wall_thickness_mm == 0.0
    assert report.dimensions == []
    assert report.valid_solids == "1 / 1"
    assert report.orientation is None
    assert report.packing is None
    assert report.exports.openable_3mf is None
    assert report.ready_to_print is True


def test_non_manifold_run_marks_part_invalid_and_not_ready(monkeypatch):
    _patch_detail(monkeypatch, _detail(manifold_state="fail"))
    report = fab_runs.build_fabrication_report("/runs/run_abc")

    part = report.parts[0]
    assert part.valid is False
    assert part.solid is False
    assert part.failure_reason == "Mesh still has open or non-manifold geometry."
    assert report.valid_solids == "0 / 1"
    assert report.ready_to_print is False  # invalid part blocks


def test_failing_printability_check_maps_to_fail_status_and_blocks(monkeypatch):
    _patch_detail(monkeypatch, _detail(slice_state="fail"))
    report = fab_runs.build_fabrication_report("/runs/run_abc")

    slice_check = next(c for c in report.printability if c.name == "slice_success")
    assert slice_check.status == Status.FAIL
    # manifold is not in printability (it drives part validity instead).
    assert all(c.name != "manifold" for c in report.printability)
    assert report.ready_to_print is False  # a FAIL check blocks


def test_review_state_maps_to_flag(monkeypatch):
    detail = _detail()
    for check in detail["validation"]:
        if check["key"] == "support_risk":
            check["state"] = "review"
    _patch_detail(monkeypatch, detail)
    report = fab_runs.build_fabrication_report("/runs/run_abc")

    support_check = next(c for c in report.printability if c.name == "support_risk")
    assert support_check.status == Status.FLAG
    assert report.ready_to_print is True  # FLAG does not block, only FAIL does


def test_agent_summary_combines_verdict_reason_and_warnings(monkeypatch):
    _patch_detail(monkeypatch, _detail(warnings=["thin walls near port", "tall overhang"]))
    report = fab_runs.build_fabrication_report("/runs/run_abc")

    assert "All available validation checks passed." in report.agent_summary
    assert "thin walls near port" in report.agent_summary
    assert "tall overhang" in report.agent_summary


def test_openable_3mf_picked_from_artifacts_excluding_gcode(monkeypatch):
    artifacts = {
        "bundle": [
            {"kind": "bundle", "path": "60_bundle/model.3mf", "present": True},
            {"kind": "bundle", "path": "70_slice/model.gcode.3mf", "present": True},
        ]
    }
    _patch_detail(monkeypatch, _detail(artifacts=artifacts))
    report = fab_runs.build_fabrication_report("/runs/run_abc")
    assert report.exports.openable_3mf == "60_bundle/model.3mf"


def test_missing_run_id_defaults_to_model(monkeypatch):
    detail = _detail(run_id="")
    _patch_detail(monkeypatch, detail)
    report = fab_runs.build_fabrication_report("/runs/run_abc")
    assert report.parts[0].id == "model"


def test_to_dict_round_trips(monkeypatch):
    import json

    _patch_detail(monkeypatch, _detail())
    report = fab_runs.build_fabrication_report("/runs/run_abc")
    payload = to_dict(report)

    assert payload["schema_version"] == 1
    assert payload["units"] == "mm"
    assert payload["target"] == "print"
    assert payload["valid_solids"] == "1 / 1"
    assert payload["ready_to_print"] is True
    assert payload["parts"][0]["valid"] is True
    statuses = {c["name"]: c["status"] for c in payload["printability"]}
    assert statuses["slice_success"] == "pass"
    assert "manifold" not in statuses

    json.dumps(payload)  # must be strictly JSON-serializable


def test_malformed_detail_degrades_without_keyerror(monkeypatch):
    # build_run_detail returns an almost-empty dict (e.g. a half-written run).
    _patch_detail(monkeypatch, {"run_id": "partial"})
    report = fab_runs.build_fabrication_report("/runs/partial")

    part = report.parts[0]
    assert part.id == "partial"
    assert part.valid is False  # no manifold check -> not valid
    assert report.printability == []  # no validation checks to map
    assert report.exports.openable_3mf is None
    assert report.ready_to_print is False
    to_dict(report)  # still serializes
