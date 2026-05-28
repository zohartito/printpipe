from __future__ import annotations

import json
from pathlib import Path

from printpipe.contracts import Artifact, ArtifactKind, StageReceipt, StageStatus
from printpipe.reports import build_run_report_dict, write_run_report
from printpipe.beta.physical import (
    PhysicalArtifact,
    build_physical_print_evidence,
    write_physical_evidence_files,
)
from printpipe.runs.detail import build_run_detail
from printpipe.runs.editing import (
    EditRecipe,
    EditScale,
    EditTargets,
    GeometryIntent,
    write_edit_recipe,
)
from printpipe.runs.paths import create_run


def test_build_run_detail_contract_for_slipper_edit_case(tmp_path: Path):
    source = tmp_path / "slipper_reference.png"
    source.write_bytes(b"fake image")
    layout = create_run(
        source,
        tmp_path / "runs",
        run_id="Slipper_TPU90A_P2S_v4_wide_upper",
    )
    generated_mesh = layout.meshgen_dir / "slipper_shape_v2c_multiview.glb"
    repaired_mesh = layout.repair_dir / "slipper_size11_v2c_repaired.stl"
    final_mesh = layout.geometry_dir / "slipper_size11_v4_wide_upper.stl"
    bundle = layout.bundle_dir / "Slipper_TPU90A_P2S_v4_wide_upper.3mf"
    slice_report = layout.slice_dir / "slice_report.json"
    for artifact_path in (
        generated_mesh,
        repaired_mesh,
        final_mesh,
        bundle,
        slice_report,
    ):
        artifact_path.write_text("fixture artifact\n", encoding="utf-8")

    stages = (
        StageReceipt(
            stage="mesh_generation",
            status=StageStatus.SUCCEEDED,
            message="Hunyuan3D multiview source selected.",
            artifacts=(
                Artifact(
                    kind=ArtifactKind.GENERATED_MESH,
                    path=generated_mesh,
                    label="Multiview GLB",
                ),
            ),
        ),
        StageReceipt(
            stage="repair",
            status=StageStatus.SUCCEEDED,
            message="Repair closed boundary edges and produced a watertight mesh.",
            artifacts=(
                Artifact(
                    kind=ArtifactKind.REPAIRED_MESH,
                    path=repaired_mesh,
                    label="Repaired STL",
                ),
            ),
            metrics={
                "watertight": True,
                "boundary_edges": 0,
                "non_manifold_edges": 0,
            },
        ),
        StageReceipt(
            stage="orient_scale",
            status=StageStatus.SUCCEEDED,
            message="Scaled to US men's 11 and widened upper target.",
            artifacts=(
                Artifact(
                    kind=ArtifactKind.ORIENTED_MESH,
                    path=final_mesh,
                    label="Final wide upper STL",
                ),
            ),
            metrics={
                "bounds_mm": [295.0, 118.0, 72.0],
                "bed_fit": "fits",
                "support_risk": "medium",
            },
        ),
        StageReceipt(
            stage="slice_report",
            status=StageStatus.SUCCEEDED,
            message="Bambu Studio slice succeeded with supports enabled.",
            artifacts=(
                Artifact(
                    kind=ArtifactKind.THREEMF,
                    path=bundle,
                    label="Bambu 3MF bundle",
                ),
                Artifact(
                    kind=ArtifactKind.SLICE_LOG,
                    path=slice_report,
                    label="Slice report",
                ),
            ),
            metrics={
                "slice_success": True,
                "print_time_minutes": 167,
                "filament_g": 84.77,
            },
        ),
    )
    settings_changes = (
        {
            "printer_label": "Bambu Lab P2S",
            "material_label": "SUNLU TPU 90A",
            "profile_label": "0.20mm Slipper TPU 90A @BBL P2S",
            "target_length_mm": 295,
            "target_width_mm": 118,
            "target_height_mm": 72,
        },
    )
    report_dict = build_run_report_dict(
        layout,
        stages=stages,
        warnings=("Original upper was too narrow; edit widens upper by 14 mm.",),
        settings_changes=settings_changes,
    )
    write_run_report(
        layout,
        stages=stages,
        warnings=report_dict["warnings"],
        settings_changes=settings_changes,
    )
    recipe = EditRecipe(
        parent_run_id=layout.run_id,
        scale=EditScale(y=1.08),
        targets_mm=EditTargets(length=295.0, width=118.0, height=72.0),
        geometry_intent=GeometryIntent(
            upper_width_delta_mm=14.0,
            opening_width_delta_mm=12.0,
            wall_thickness_mm=3.2,
            flat_base=True,
        ),
        support_strategy="snug_tree_auto",
        instruction="Widen the top upper; do not lengthen the sole.",
    )
    write_edit_recipe(layout.root, recipe)

    detail = build_run_detail(layout.root)

    assert detail["schema_version"] == 1
    assert detail["run_id"] == "Slipper_TPU90A_P2S_v4_wide_upper"
    assert detail["input"]["kind"] == "image"
    assert detail["parent_run"] is None
    assert detail["settings"]["target_length_mm"] == 295
    assert detail["printer"] == {"label": "Bambu Lab P2S"}
    assert detail["material"] == {"label": "SUNLU TPU 90A"}
    assert detail["profile"] == {"label": "0.20mm Slipper TPU 90A @BBL P2S"}
    assert detail["geometry"]["bounds_mm"] == [295.0, 118.0, 72.0]
    assert detail["geometry"]["filament_g"] == 84.77
    assert detail["rebuild"] == {
        "available": True,
        "mode": "edit_recipe",
        "creates": "new_run",
    }
    assert detail["print_verdict"] == {
        "state": "review",
        "label": "Review before print",
        "reason": "Warnings remain, but no blocking validation checks failed.",
    }
    assert [(check["key"], check["state"]) for check in detail["validation"]] == [
        ("manifold", "pass"),
        ("bed_fit", "pass"),
        ("material_profile", "pass"),
        ("support_risk", "review"),
        ("slice_success", "pass"),
    ]
    assert [stage["key"] for stage in detail["pipeline"]] == [
        "input_reference",
        "mesh_generation",
        "repair",
        "orient_scale",
        "print_profile",
        "bundle",
        "slice_report",
    ]
    assert detail["edit_recipe"]["geometry_intent"]["upper_width_delta_mm"] == 14.0
    assert detail["artifacts"]["3mf"][0]["label"] == "Bambu 3MF bundle"


def test_slipper_run_detail_fixture_matches_ui_contract():
    fixture_path = Path("examples/slipper_run_detail_fixture.json")

    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

    assert fixture["schema_version"] == 1
    assert fixture["run_id"] == "Slipper_TPU90A_P2S_v4_wide_upper"
    assert fixture["printer"]["label"] == "Bambu Lab P2S"
    assert fixture["material"]["label"] == "SUNLU TPU 90A"
    assert fixture["print_verdict"]["state"] == "review"
    assert [check["key"] for check in fixture["validation"]] == [
        "manifold",
        "bed_fit",
        "material_profile",
        "support_risk",
        "slice_success",
    ]
    assert [stage["key"] for stage in fixture["pipeline"]] == [
        "input_reference",
        "mesh_generation",
        "repair",
        "orient_scale",
        "print_profile",
        "bundle",
        "slice_report",
    ]
    assert fixture["edit_recipe"]["support_strategy"] == "snug_tree_auto"


def test_run_detail_fails_manifold_when_any_topology_metric_is_bad(tmp_path: Path):
    source = tmp_path / "reference.png"
    source.write_bytes(b"fake image")
    layout = create_run(source, tmp_path / "runs", run_id="bad-topology")
    stages = (
        StageReceipt(
            stage="repair",
            status=StageStatus.SUCCEEDED,
            message="Repair reported mixed topology metrics.",
            metrics={
                "watertight": False,
                "boundary_edges": 0,
                "non_manifold_edges": 12,
            },
        ),
    )
    write_run_report(layout, stages=stages)

    detail = build_run_detail(layout.root)

    manifold = next(check for check in detail["validation"] if check["key"] == "manifold")
    assert manifold["state"] == "fail"
    assert detail["print_verdict"]["state"] == "blocked"


def test_run_detail_uses_real_bed_fit_and_slice_receipt_metrics(tmp_path: Path):
    source = tmp_path / "mesh.stl"
    source.write_text("solid fake\nendsolid fake\n", encoding="utf-8")
    layout = create_run(source, tmp_path / "runs", run_id="real-receipt-metrics")
    stages = (
        StageReceipt(
            stage="geometry.write_bed_fit_preview_artifacts",
            status=StageStatus.SUCCEEDED,
            message="wrote bounds-only bed-fit preview artifacts",
            metrics={"fits": True, "min_margin_mm": 18.5},
        ),
        StageReceipt(
            stage="slice",
            status=StageStatus.FAILED,
            message="Bambu CLI slice failed: slicer terminated by signal 11 (SIGSEGV).",
            metrics={
                "slice_requested": True,
                "return_code": -11,
                "errors": ("slicer terminated by signal 11 (SIGSEGV)",),
            },
        ),
    )
    write_run_report(layout, stages=stages)

    detail = build_run_detail(layout.root)

    validation = {check["key"]: check for check in detail["validation"]}
    assert detail["geometry"]["bed_fit"] == "fits"
    assert validation["bed_fit"]["state"] == "pass"
    assert "18.5 mm minimum margin" in validation["bed_fit"]["detail"]
    assert validation["slice_success"]["state"] == "fail"
    assert "SIGSEGV" in validation["slice_success"]["detail"]
    assert detail["print_verdict"]["state"] == "blocked"


def test_run_detail_contract_loads_physical_evidence_packet(tmp_path: Path):
    source = tmp_path / "reference.png"
    source.write_bytes(b"fake image")
    layout = create_run(source, tmp_path / "runs", run_id="run-physical-001")
    photo = layout.root / "90_physical" / "artifacts" / "coupon.jpg"
    photo.parent.mkdir(parents=True)
    photo.write_bytes(b"photo")
    evidence = build_physical_print_evidence(
        run_id=layout.run_id,
        material="SUNLU TPU 90A",
        printer="Bambu Lab P2S",
        object_label="flex coupon",
        print_type="coupon",
        print_status="passed",
        operator="Zohar",
        filament_drying="50 C for 6 h",
        layer_bonding="no splits after bending",
        flex_recovery="returned flat after 20 flexes",
        artifacts=(
            PhysicalArtifact(
                label="Flexed coupon photo",
                path="90_physical/artifacts/coupon.jpg",
                kind="photo",
            ),
        ),
    )
    write_physical_evidence_files(run_root=layout.root, evidence=evidence)

    detail = build_run_detail(layout.root)

    assert detail["physical_evidence"]["available"] is True
    assert detail["physical_evidence"]["print_status"] == "passed"
    assert detail["physical_evidence"]["object_label"] == "flex coupon"
    assert detail["physical_evidence"]["operator"] == "Zohar"
    assert detail["physical_evidence"]["missing_required_evidence"] == []
    assert detail["physical_evidence"]["packet_paths"] == {
        "json": "90_physical/physical_evidence.json",
        "markdown": "90_physical/physical_evidence.md",
    }
