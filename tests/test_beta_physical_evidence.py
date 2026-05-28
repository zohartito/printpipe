from __future__ import annotations

import json
from pathlib import Path

from printpipe.beta.physical import (
    PHYSICAL_EVIDENCE_REQUIRED_HEADINGS,
    PhysicalArtifact,
    build_physical_print_evidence,
    missing_required_evidence,
    render_physical_evidence_markdown,
)


def test_tpu_coupon_evidence_serializes_to_json_friendly_dict(tmp_path: Path) -> None:
    photo = tmp_path / "runs" / "run-tpu-001" / "90_physical" / "coupon-flex.jpg"

    evidence = build_physical_print_evidence(
        run_id="run-tpu-001",
        material="SUNLU TPU 90A",
        printer="Bambu Lab P2S",
        object_label="40 x 15 x 3 mm flex coupon",
        print_type="coupon",
        print_status="passed",
        operator="Zohar",
        started_at="2026-05-28T08:00:00-07:00",
        completed_at="2026-05-28T08:24:00-07:00",
        slice_status="Bambu GUI slice accepted",
        filament_drying="50 C for 6 h in AMS 2 Pro dryer before print",
        bed_prep="PEI plate cleaned with IPA; glue used as release layer",
        first_layer="continuous first layer, no lifting",
        adhesion="held through print, released after cooling",
        stringing="minor hairs between coupon ends",
        layer_bonding="no visible splits after repeated bending",
        flex_recovery="returned flat after 20 hand flexes",
        support_removal="no supports used",
        dimensions_mm={"x": 40.2, "y": 15.1, "z": 3.0},
        artifacts=(
            PhysicalArtifact(
                label="Flexed coupon photo",
                path=photo,
                kind="photo",
                notes="shows coupon bent by hand",
            ),
        ),
        notes=("Ready to try a tiny TPU object with same profile.",),
    )

    payload = evidence.to_dict()

    assert payload == {
        "schema_version": 1,
        "run_id": "run-tpu-001",
        "material": "SUNLU TPU 90A",
        "printer": "Bambu Lab P2S",
        "object_label": "40 x 15 x 3 mm flex coupon",
        "print_type": "coupon",
        "print_status": "passed",
        "operator": "Zohar",
        "started_at": "2026-05-28T08:00:00-07:00",
        "completed_at": "2026-05-28T08:24:00-07:00",
        "slice_status": "Bambu GUI slice accepted",
        "filament_drying": "50 C for 6 h in AMS 2 Pro dryer before print",
        "bed_prep": "PEI plate cleaned with IPA; glue used as release layer",
        "first_layer": "continuous first layer, no lifting",
        "adhesion": "held through print, released after cooling",
        "warping": "",
        "stringing": "minor hairs between coupon ends",
        "layer_bonding": "no visible splits after repeated bending",
        "flex_recovery": "returned flat after 20 hand flexes",
        "support_removal": "no supports used",
        "dimensions_mm": {"x": 40.2, "y": 15.1, "z": 3.0},
        "artifacts": [
            {
                "label": "Flexed coupon photo",
                "path": str(photo),
                "kind": "photo",
                "notes": "shows coupon bent by hand",
            }
        ],
        "notes": ["Ready to try a tiny TPU object with same profile."],
    }
    json.dumps(payload)
    assert missing_required_evidence(evidence) == []


def test_missing_required_evidence_is_material_specific() -> None:
    tpu = build_physical_print_evidence(
        run_id="run-tpu-missing",
        material="Bambu TPU 95A",
        printer="Bambu Lab P2S",
        object_label="flex coupon",
        print_type="coupon",
        print_status="failed",
    )
    petg = build_physical_print_evidence(
        run_id="run-petg-missing",
        material="Bambu PETG-CF",
        printer="Bambu Lab P2S",
        object_label="stand bracket",
        print_type="small_object",
        print_status="partial",
    )
    pla = build_physical_print_evidence(
        run_id="run-pla-missing",
        material="Bambu PLA Basic",
        printer="Bambu Lab P2S",
        object_label="tiny tetrahedron",
        print_type="small_object",
        print_status="passed",
    )

    assert missing_required_evidence(tpu) == [
        "operator",
        "photo artifact",
        "filament_drying",
        "layer_bonding",
        "flex_recovery",
    ]
    assert missing_required_evidence(petg) == [
        "operator",
        "photo artifact",
        "first_layer",
        "adhesion",
        "warping",
        "stringing",
    ]
    assert missing_required_evidence(pla) == [
        "operator",
        "photo artifact",
        "first_layer",
        "adhesion",
    ]


def test_not_printed_evidence_does_not_require_photos_yet() -> None:
    evidence = build_physical_print_evidence(
        run_id="run-not-printed",
        material="Generic PLA",
        printer="Bambu Lab P2S",
        object_label="tiny tetrahedron",
        print_type="small_object",
        print_status="not_printed",
    )

    assert missing_required_evidence(evidence) == ["operator"]


def test_render_physical_evidence_markdown_contains_required_sections(tmp_path: Path) -> None:
    photo = tmp_path / "coupon.jpg"
    evidence = build_physical_print_evidence(
        run_id="run-tpu-001",
        material="SUNLU TPU 90A",
        printer="Bambu Lab P2S",
        object_label="flex coupon",
        print_type="coupon",
        print_status="passed",
        operator="Zohar",
        filament_drying="50 C for 6 h",
        layer_bonding="no splits",
        flex_recovery="returned flat",
        artifacts=(PhysicalArtifact(label="Coupon photo", path=photo, kind="photo"),),
    )

    markdown = render_physical_evidence_markdown(evidence)

    for heading in PHYSICAL_EVIDENCE_REQUIRED_HEADINGS:
        assert f"## {heading}" in markdown
    assert "- Run ID: run-tpu-001" in markdown
    assert "- Print status: passed" in markdown
    assert "- Coupon photo: " in markdown
    assert "No missing required evidence" in markdown
