from __future__ import annotations

import json
from pathlib import Path

from printpipe.calibration.flex_coupon import write_flex_coupon_artifacts
from printpipe.contracts import ArtifactKind, StageStatus
from printpipe.geometry import read_ascii_stl_vertices
from printpipe.pipeline import run_existing_mesh_pipeline


STL_FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "objects"
    / "existing_stl_pipeline"
    / "tiny_tetrahedron.stl"
)


def test_write_flex_coupon_artifacts_creates_ascii_stl_and_sidecar(tmp_path: Path):
    receipt = write_flex_coupon_artifacts(
        tmp_path,
        material="SUNLU TPU 90A",
        use_case="slipper",
    )

    assert receipt.stage == "validation.flex_coupon"
    assert receipt.status == StageStatus.SUCCEEDED
    mesh_artifact = receipt.artifacts[0]
    report_artifact = receipt.artifacts[1]
    assert mesh_artifact.kind == ArtifactKind.CALIBRATION_MESH
    assert mesh_artifact.path.name == "flex_coupon_40x15x3.stl"
    assert report_artifact.path.name == "flex_coupon_40x15x3.json"

    vertices = read_ascii_stl_vertices(mesh_artifact.path)
    xs = [vertex[0] for vertex in vertices]
    ys = [vertex[1] for vertex in vertices]
    zs = [vertex[2] for vertex in vertices]
    assert max(xs) - min(xs) == 40.0
    assert max(ys) - min(ys) == 15.0
    assert max(zs) - min(zs) == 3.0

    sidecar = json.loads(report_artifact.path.read_text(encoding="utf-8"))
    assert sidecar["material"] == "SUNLU TPU 90A"
    assert sidecar["use_case"] == "slipper"
    assert sidecar["dimensions_mm"] == {"length": 40.0, "width": 15.0, "height": 3.0}
    assert sidecar["print_validation"] == [
        "bed adhesion",
        "flex recovery",
        "interlayer bonding",
        "support/brim removability",
    ]


def test_tpu_pipeline_report_includes_flex_coupon_validation_artifact(tmp_path: Path):
    result = run_existing_mesh_pipeline(
        STL_FIXTURE,
        tmp_path / "runs",
        material="SUNLU TPU 90A",
        use_case="slipper",
    )

    stages = {receipt.stage: receipt for receipt in result.stages}
    assert stages["validation.flex_coupon"].status == StageStatus.SUCCEEDED

    report = json.loads((result.layout.reports_dir / "run_report.json").read_text(encoding="utf-8"))
    assert ("calibration_mesh", "40_geometry/flex_coupon_40x15x3.stl") in {
        (artifact["kind"], artifact["path"]) for artifact in report["artifacts"]
    }
    checklist = {item["id"]: item for item in report["pre_print_checklist"]}
    assert checklist["flex_coupon_first"]["status"] == "required"
    assert checklist["flex_coupon_first"]["metadata"]["coupon_artifact"] == (
        "40_geometry/flex_coupon_40x15x3.stl"
    )
