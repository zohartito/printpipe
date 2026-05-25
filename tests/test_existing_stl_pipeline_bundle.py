from __future__ import annotations

import json
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from printpipe.bambu.threemf import CORE_NS, validate_bundle
from printpipe.bambu.threemf.mesh_adapter import read_ascii_stl
from printpipe.contracts import ArtifactKind, StageStatus
from printpipe.pipeline import run_existing_mesh_pipeline


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "objects" / "existing_stl_pipeline"
STL_FIXTURE = FIXTURE_DIR / "tiny_tetrahedron.stl"
METADATA_FIXTURE = FIXTURE_DIR / "metadata.json"


def test_existing_ascii_stl_runs_pipeline_and_writes_bundle_in_run_dir(tmp_path: Path):
    metadata = json.loads(METADATA_FIXTURE.read_text(encoding="utf-8"))
    runs_dir = tmp_path / "runs"

    result = run_existing_mesh_pipeline(STL_FIXTURE, runs_dir)

    stages = {receipt.stage: receipt for receipt in result.stages}
    assert stages["classify_input"].status == StageStatus.SUCCEEDED
    assert stages["route_existing_mesh"].status == StageStatus.SUCCEEDED
    assert stages["meshgen"].status == StageStatus.SUCCEEDED
    assert stages["meshgen"].metrics["provider_id"] == "existing_mesh"
    assert stages["mesh_repair"].status in {StageStatus.SUCCEEDED, StageStatus.SKIPPED}
    assert stages["geometry.write_oriented_ascii_stl_artifacts"].status == StageStatus.SUCCEEDED
    assert stages["geometry.write_bed_fit_preview_artifacts"].status == StageStatus.SUCCEEDED
    assert stages["bundle"].status == StageStatus.SUCCEEDED
    assert stages["bundle_validation"].status == StageStatus.SUCCEEDED

    imported_mesh = result.layout.meshgen_dir / STL_FIXTURE.name
    assert imported_mesh.exists()
    assert imported_mesh.read_text(encoding="ascii") == STL_FIXTURE.read_text(encoding="ascii")
    assert stages["meshgen"].artifacts[0].kind == ArtifactKind.GENERATED_MESH
    assert stages["meshgen"].artifacts[0].path == imported_mesh
    assert stages["mesh_repair"].artifacts[-1].path == (
        result.layout.repair_dir / "tiny_tetrahedron_repair.json"
    )

    oriented_mesh = result.layout.geometry_dir / "tiny_tetrahedron_oriented.stl"
    bed_fit_svg = result.layout.reports_dir / "bed_fit.svg"
    bed_fit_json = result.layout.reports_dir / "bed_fit.json"
    bundle_path = result.layout.bundle_dir / metadata["bundle"]["filename"]
    validation_receipt = result.layout.bundle_dir / "existing_stl_tiny_tetrahedron_bundle_validation.json"

    artifact_paths = {artifact.path for artifact in result.artifacts}
    assert oriented_mesh in artifact_paths
    assert bed_fit_svg in artifact_paths
    assert bed_fit_json in artifact_paths
    assert bundle_path in artifact_paths
    assert validation_receipt in artifact_paths
    assert stages["bundle"].artifacts[0].kind == ArtifactKind.THREEMF
    assert stages["bundle"].artifacts[0].path == bundle_path

    report_path = result.layout.reports_dir / "run_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["run_id"] == result.layout.run_id
    report_stages = {
        (stage["stage"], stage["status"]) for stage in report["stages"]
    }
    assert ("meshgen", "succeeded") in report_stages
    assert ("geometry.write_oriented_ascii_stl_artifacts", "succeeded") in report_stages
    assert ("geometry.write_bed_fit_preview_artifacts", "succeeded") in report_stages
    assert ("bundle", "succeeded") in report_stages
    assert ("bundle_validation", "succeeded") in report_stages

    mesh = read_ascii_stl(oriented_mesh)
    assert len(mesh.vertices) == metadata["expected_mesh"]["vertices"]
    assert len(mesh.triangles) == metadata["expected_mesh"]["triangles"]

    validation = validate_bundle(bundle_path)
    assert validation.ok, validation.errors

    with zipfile.ZipFile(bundle_path) as archive:
        model = ET.fromstring(archive.read("3D/3dmodel.model"))
        project_settings = json.loads(archive.read("Metadata/project_settings.config"))

    ns = {"core": CORE_NS}
    assert len(model.findall(".//core:vertex", ns)) == metadata["expected_mesh"]["vertices"]
    assert len(model.findall(".//core:triangle", ns)) == metadata["expected_mesh"]["triangles"]
    assert project_settings["filament_settings_id"] == [
        metadata["profile_ids"]["filament_settings_id"]
    ]
    assert project_settings["print_settings_id"] == metadata["profile_ids"]["print_settings_id"]
    assert project_settings["printer_settings_id"] == metadata["profile_ids"]["printer_settings_id"]
