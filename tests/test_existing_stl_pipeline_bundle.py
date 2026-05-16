from __future__ import annotations

import json
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from printpipe.bambu.threemf import BambuProfileIds, CORE_NS, GuiSafeTransform, validate_bundle
from printpipe.bambu.threemf.mesh_adapter import read_ascii_stl, write_bundle_from_ascii_stl
from printpipe.contracts import ArtifactKind, StageStatus
from printpipe.pipeline import run_existing_mesh_pipeline


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "objects" / "existing_stl_pipeline"
STL_FIXTURE = FIXTURE_DIR / "tiny_tetrahedron.stl"
METADATA_FIXTURE = FIXTURE_DIR / "metadata.json"


def test_existing_ascii_stl_runs_pipeline_and_writes_bundle_in_run_dir(tmp_path: Path):
    metadata = json.loads(METADATA_FIXTURE.read_text(encoding="utf-8"))
    profile_ids = BambuProfileIds(**metadata["profile_ids"])
    object_name = metadata["object"]["name"]
    transform = GuiSafeTransform.bed_center(
        metadata["bed"]["width_mm"],
        metadata["bed"]["depth_mm"],
    )
    runs_dir = tmp_path / "runs"

    result = run_existing_mesh_pipeline(STL_FIXTURE, runs_dir)

    stages = {receipt.stage: receipt for receipt in result.stages}
    assert stages["classify_input"].status == StageStatus.SUCCEEDED
    assert stages["route_existing_mesh"].status == StageStatus.SUCCEEDED
    assert stages["meshgen"].status == StageStatus.SUCCEEDED
    assert stages["meshgen"].metrics["provider_id"] == "existing_mesh"

    imported_mesh = result.layout.meshgen_dir / STL_FIXTURE.name
    assert imported_mesh.exists()
    assert imported_mesh.read_text(encoding="ascii") == STL_FIXTURE.read_text(encoding="ascii")
    assert stages["meshgen"].artifacts[0].kind == ArtifactKind.GENERATED_MESH
    assert stages["meshgen"].artifacts[0].path == imported_mesh

    report_path = result.layout.reports_dir / "run_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["run_id"] == result.layout.run_id
    assert ("meshgen", "succeeded") in {
        (stage["stage"], stage["status"]) for stage in report["stages"]
    }

    mesh = read_ascii_stl(imported_mesh)
    assert len(mesh.vertices) == metadata["expected_mesh"]["vertices"]
    assert len(mesh.triangles) == metadata["expected_mesh"]["triangles"]

    bundle_path = result.layout.bundle_dir / metadata["bundle"]["filename"]
    written_bundle = write_bundle_from_ascii_stl(
        imported_mesh,
        bundle_path,
        profile_ids,
        object_name=object_name,
        transform=transform,
    )

    validation = validate_bundle(written_bundle)
    assert written_bundle == bundle_path
    assert written_bundle.parent == result.layout.bundle_dir
    assert validation.ok, validation.errors

    with zipfile.ZipFile(written_bundle) as archive:
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
