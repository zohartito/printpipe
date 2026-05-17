from __future__ import annotations

import json

from printpipe.preflight import PreflightContext, build_pre_print_checklist


def test_tpu_checklist_marks_drying_external_spool_and_coupon_required():
    checklist = build_pre_print_checklist(
        PreflightContext(
            material="SUNLU TPU 90A",
            printer="Bambu Lab P2S",
            use_case="wearable slipper",
            slice_gate_status="passed",
        )
    )

    by_id = {item["id"]: item for item in checklist}
    assert list(by_id) == [
        "dry_filament",
        "feed_path",
        "layer_preview",
        "slice_gate",
        "first_layer_inspection",
        "flex_coupon_first",
    ]
    assert by_id["dry_filament"]["status"] == "required"
    assert "50 C for 4-8 h" in by_id["dry_filament"]["detail"]
    assert by_id["feed_path"]["status"] == "required"
    assert "external spool" in by_id["feed_path"]["detail"].lower()
    assert "AMS" in by_id["feed_path"]["detail"]
    assert by_id["flex_coupon_first"]["status"] == "required"
    assert "wearable slipper" in by_id["flex_coupon_first"]["detail"]
    assert by_id["slice_gate"]["status"] == "passed"
    json.dumps(checklist)


def test_petg_checklist_is_generic_and_keeps_flex_coupon_not_applicable():
    checklist = build_pre_print_checklist(
        material="PETG",
        printer="Bambu Lab P2S",
        use_case="bracket",
        slice_gate_status=False,
    )

    by_id = {item["id"]: item for item in checklist}
    assert by_id["dry_filament"]["status"] == "recommended"
    assert "PETG" in by_id["dry_filament"]["title"]
    assert by_id["feed_path"]["status"] == "review"
    assert "normal spool path" in by_id["feed_path"]["detail"].lower()
    assert by_id["layer_preview"]["status"] == "required"
    assert by_id["slice_gate"]["status"] == "failed"
    assert by_id["flex_coupon_first"]["status"] == "not_applicable"
    assert "flexible" in by_id["flex_coupon_first"]["detail"].lower()


def test_pla_checklist_accepts_plain_kwargs_and_unknown_slice_gate():
    checklist = build_pre_print_checklist(
        material="PLA Matte",
        printer="Bambu Lab A1",
        use_case="decorative object",
    )

    by_id = {item["id"]: item for item in checklist}
    assert by_id["dry_filament"]["status"] == "optional"
    assert by_id["feed_path"]["status"] == "review"
    assert by_id["slice_gate"]["status"] == "unknown"
    assert by_id["slice_gate"]["detail"] == "Slice gate has not run yet."
    assert all("category" in item for item in checklist)
    json.dumps(checklist)


def test_slice_gate_mapping_preserves_warnings_and_error_counts():
    checklist = build_pre_print_checklist(
        material="TPU",
        printer="Bambu Lab P2S",
        use_case="test coupon",
        slice_gate_status={
            "status": "warning",
            "warnings": ["floating cantilever"],
            "errors": [],
        },
    )

    slice_item = {item["id"]: item for item in checklist}["slice_gate"]
    assert slice_item["status"] == "warning"
    assert slice_item["metadata"] == {
        "warnings": ["floating cantilever"],
        "errors": [],
    }
