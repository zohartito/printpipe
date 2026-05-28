from __future__ import annotations

import json
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest

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


def test_tpu_bundle_embeds_resolved_bambu_profile_settings_for_cli(
    tmp_path: Path,
    monkeypatch,
):
    profile_root = tmp_path / "profiles" / "BBL"
    _write_profile(
        profile_root / "machine" / "fdm_bbl_3dp_001_common.json",
        {
            "name": "fdm_bbl_3dp_001_common",
            "type": "machine",
            "printer_model": "Bambu Lab P2S",
            "printable_area": ["0x0", "256x0", "256x256", "0x256"],
            "machine_start_gcode": "G28 ; home from base machine",
        },
    )
    _write_profile(
        profile_root / "machine" / "Bambu Lab P2S 0.4 nozzle.json",
        {
            "name": "Bambu Lab P2S 0.4 nozzle",
            "type": "machine",
            "inherits": "fdm_bbl_3dp_001_common",
            "nozzle_type": ["hardened_steel"],
        },
    )
    _write_profile(
        profile_root / "process" / "fdm_process_single_0.20.json",
        {
            "name": "fdm_process_single_0.20",
            "type": "process",
            "wall_loops": "2",
            "base_process_marker": "from-base-process",
        },
    )
    _write_profile(
        profile_root / "process" / "0.20mm Standard @BBL P2S.json",
        {
            "name": "0.20mm Standard @BBL P2S",
            "type": "process",
            "inherits": "fdm_process_single_0.20",
            "compatible_printers": ["Bambu Lab P2S 0.4 nozzle"],
        },
    )
    _write_profile(
        profile_root / "filament" / "Bambu TPU 90A @base.json",
        {
            "name": "Bambu TPU 90A @base",
            "type": "filament",
            "filament_type": ["TPU"],
            "filament_max_volumetric_speed": ["2.8"],
        },
    )
    _write_profile(
        profile_root / "filament" / "Bambu TPU 90A @BBL P2S.json",
        {
            "name": "Bambu TPU 90A @BBL P2S",
            "type": "filament",
            "inherits": "Bambu TPU 90A @base",
            "compatible_printers": ["Bambu Lab P2S 0.4 nozzle"],
        },
    )
    monkeypatch.setenv("PRINTPIPE_BAMBU_PROFILE_ROOTS", str(profile_root))

    result = run_existing_mesh_pipeline(
        STL_FIXTURE,
        tmp_path / "runs",
        material="SUNLU TPU 90A",
    )
    bundle_path = next(
        artifact.path
        for artifact in result.artifacts
        if artifact.kind == ArtifactKind.THREEMF
    )

    with zipfile.ZipFile(bundle_path) as archive:
        project_settings = json.loads(archive.read("Metadata/project_settings.config"))

    assert project_settings["printable_area"] == ["0x0", "256x0", "256x256", "0x256"]
    assert project_settings["machine_start_gcode"] == "G28 ; home from base machine"
    assert project_settings["base_process_marker"] == "from-base-process"
    assert project_settings["wall_loops"] == ["3"]
    assert project_settings["filament_type"] == ["TPU"]
    assert project_settings["filament_settings_id"] == ["SUNLU TPU 90A Slipper @BBL P2S"]
    assert project_settings["print_settings_id"] == "0.20mm Slipper TPU 90A @BBL P2S"
    assert project_settings["support_style"] == ["snug"]
    assert project_settings["brim_object_gap"] == ["0.12"]


def test_pla_bundle_merges_pla_material_overrides_with_resolved_profiles(
    tmp_path: Path,
    monkeypatch,
):
    profile_root = tmp_path / "profiles" / "BBL"
    _write_minimal_p2s_profiles(profile_root)
    _write_profile(
        profile_root / "filament" / "Generic PLA @BBL P2S.json",
        {
            "name": "Generic PLA @BBL P2S",
            "type": "filament",
            "filament_type": ["ABS"],
            "filament_vendor": ["Unknown"],
        },
    )
    monkeypatch.setenv("PRINTPIPE_BAMBU_PROFILE_ROOTS", str(profile_root))

    result = run_existing_mesh_pipeline(
        STL_FIXTURE,
        tmp_path / "runs",
        material="PLA+",
    )
    bundle_path = next(
        artifact.path
        for artifact in result.artifacts
        if artifact.kind == ArtifactKind.THREEMF
    )

    with zipfile.ZipFile(bundle_path) as archive:
        project_settings = json.loads(archive.read("Metadata/project_settings.config"))

    assert project_settings["filament_type"] == ["PLA"]
    assert project_settings["filament_vendor"] == ["Generic PLA+"]
    assert project_settings["base_process_marker"] == "from-base-process"
    assert project_settings["wall_loops"] == ["2"]
    assert project_settings["filament_settings_id"] == ["Generic PLA+"]


def test_petg_bundle_merges_petg_material_overrides_with_resolved_profiles(
    tmp_path: Path,
    monkeypatch,
):
    profile_root = tmp_path / "profiles" / "BBL"
    _write_minimal_p2s_profiles(profile_root)
    _write_profile(
        profile_root / "filament" / "Generic PLA @BBL P2S.json",
        {
            "name": "Generic PLA @BBL P2S",
            "type": "filament",
            "filament_type": ["PLA"],
            "nozzle_temperature": ["220"],
        },
    )
    _write_profile(
        profile_root / "filament" / "Generic PETG @BBL P2S.json",
        {
            "name": "Generic PETG @BBL P2S",
            "type": "filament",
            "filament_type": ["PETG"],
            "nozzle_temperature": ["240"],
            "textured_plate_temp": ["65"],
        },
    )
    monkeypatch.setenv("PRINTPIPE_BAMBU_PROFILE_ROOTS", str(profile_root))

    result = run_existing_mesh_pipeline(
        STL_FIXTURE,
        tmp_path / "runs",
        material="PETG",
    )
    bundle_path = next(
        artifact.path
        for artifact in result.artifacts
        if artifact.kind == ArtifactKind.THREEMF
    )

    with zipfile.ZipFile(bundle_path) as archive:
        project_settings = json.loads(archive.read("Metadata/project_settings.config"))

    assert project_settings["filament_type"] == ["PETG"]
    assert project_settings["filament_vendor"] == ["Generic"]
    assert project_settings["nozzle_temperature"] == ["250"]
    assert project_settings["textured_plate_temp"] == ["70"]
    assert project_settings["filament_max_volumetric_speed"] == ["8"]
    assert project_settings["brim_object_gap"] == "0.1"
    assert project_settings["curr_bed_type"] == "Textured PEI Plate"
    assert project_settings["filament_settings_id"] == ["Generic PETG"]


@pytest.mark.parametrize(
    (
        "material",
        "profile_name",
        "expected_filament_id",
        "expected_filament_type",
        "expected_nozzle_temp",
        "expected_bed_temp",
        "expected_mvs",
    ),
    [
        ("ABS", "Generic ABS @BBL P2S", "Generic ABS", ["ABS"], ["260"], ["100"], ["10"]),
        ("ASA", "Generic ASA @BBL P2S", "Generic ASA", ["ASA"], ["255"], ["100"], ["8"]),
        ("PC", "Generic PC @BBL P2S", "Generic PC", ["PC"], ["280"], ["100"], ["8"]),
        ("PA", "Generic PA @BBL P2S", "Generic PA", ["PA"], ["260"], ["90"], ["8"]),
        (
            "PA-CF",
            "Generic PA-CF @BBL P2S",
            "Generic PA-CF",
            ["PA-CF"],
            ["285"],
            ["100"],
            ["6"],
        ),
    ],
)
def test_engineering_material_bundles_merge_material_overrides(
    tmp_path: Path,
    monkeypatch,
    material: str,
    profile_name: str,
    expected_filament_id: str,
    expected_filament_type: list[str],
    expected_nozzle_temp: list[str],
    expected_bed_temp: list[str],
    expected_mvs: list[str],
):
    profile_root = tmp_path / "profiles" / "BBL"
    _write_minimal_p2s_profiles(profile_root)
    _write_profile(
        profile_root / "filament" / f"{profile_name}.json",
        {
            "name": profile_name,
            "type": "filament",
            "filament_type": ["PLA"],
            "nozzle_temperature": ["220"],
            "textured_plate_temp": ["55"],
            "filament_max_volumetric_speed": ["20"],
        },
    )
    monkeypatch.setenv("PRINTPIPE_BAMBU_PROFILE_ROOTS", str(profile_root))

    result = run_existing_mesh_pipeline(
        STL_FIXTURE,
        tmp_path / "runs",
        material=material,
    )
    bundle_path = next(
        artifact.path
        for artifact in result.artifacts
        if artifact.kind == ArtifactKind.THREEMF
    )

    with zipfile.ZipFile(bundle_path) as archive:
        project_settings = json.loads(archive.read("Metadata/project_settings.config"))

    assert project_settings["filament_settings_id"] == [expected_filament_id]
    assert project_settings["filament_type"] == expected_filament_type
    assert project_settings["nozzle_temperature"] == expected_nozzle_temp
    assert project_settings["textured_plate_temp"] == expected_bed_temp
    assert project_settings["filament_max_volumetric_speed"] == expected_mvs
    assert project_settings["curr_bed_type"] == "Textured PEI Plate"
    assert project_settings["brim_type"] == "outer_only"


def _write_minimal_p2s_profiles(profile_root: Path) -> None:
    _write_profile(
        profile_root / "machine" / "fdm_bbl_3dp_001_common.json",
        {
            "name": "fdm_bbl_3dp_001_common",
            "type": "machine",
            "printer_model": "Bambu Lab P2S",
            "printable_area": ["0x0", "256x0", "256x256", "0x256"],
            "machine_start_gcode": "G28 ; home from base machine",
        },
    )
    _write_profile(
        profile_root / "machine" / "Bambu Lab P2S 0.4 nozzle.json",
        {
            "name": "Bambu Lab P2S 0.4 nozzle",
            "type": "machine",
            "inherits": "fdm_bbl_3dp_001_common",
            "nozzle_type": ["hardened_steel"],
        },
    )
    _write_profile(
        profile_root / "process" / "fdm_process_single_0.20.json",
        {
            "name": "fdm_process_single_0.20",
            "type": "process",
            "wall_loops": "5",
            "base_process_marker": "from-base-process",
        },
    )
    _write_profile(
        profile_root / "process" / "0.20mm Standard @BBL P2S.json",
        {
            "name": "0.20mm Standard @BBL P2S",
            "type": "process",
            "inherits": "fdm_process_single_0.20",
            "compatible_printers": ["Bambu Lab P2S 0.4 nozzle"],
        },
    )


def _write_profile(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
