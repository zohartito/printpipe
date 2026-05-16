from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest

from printpipe.bambu.threemf import (
    CORE_NS,
    PRODUCTION_NS,
    REQUIRED_MEMBERS,
    BambuProfileIds,
    GuiSafeTransform,
    MeshGeometry,
    build_model_xml,
    validate_bundle,
    write_bundle,
)


def tiny_tetrahedron() -> MeshGeometry:
    return MeshGeometry(
        vertices=(
            (0.0, 0.0, 0.0),
            (10.0, 0.0, 0.0),
            (0.0, 10.0, 0.0),
            (0.0, 0.0, 10.0),
        ),
        triangles=(
            (0, 2, 1),
            (0, 1, 3),
            (1, 2, 3),
            (2, 0, 3),
        ),
    )


def profile_ids() -> BambuProfileIds:
    return BambuProfileIds(
        filament_settings_id="Generic PLA",
        print_settings_id="0.20mm Standard",
        printer_settings_id="Bambu Lab P2S 0.4 nozzle",
        printer_model="Bambu Lab P2S",
        printer_variant="0.4",
        nozzle_diameter="0.4",
        printable_height="256",
    )


def metadata_by_name(root: ET.Element) -> dict[str, str]:
    ns = {"core": CORE_NS}
    values: dict[str, str] = {}
    for metadata in root.findall("core:metadata", ns):
        values[metadata.attrib["name"]] = metadata.text or ""
    return values


def test_write_bundle_emits_required_members_and_bambu_native_model(tmp_path: Path):
    bundle_path = tmp_path / "tiny.3mf"

    write_bundle(
        bundle_path,
        mesh=tiny_tetrahedron(),
        object_name="tiny & printable",
        profile_ids=profile_ids(),
        transform=GuiSafeTransform.bed_center(256, 256),
    )

    with zipfile.ZipFile(bundle_path) as archive:
        names = set(archive.namelist())
        model_xml = archive.read("3D/3dmodel.model")

    assert REQUIRED_MEMBERS <= names
    assert b'xmlns:BambuStudio="http://schemas.bambulab.com/package/2021"' in model_xml

    root = ET.fromstring(model_xml)
    ns = {"core": CORE_NS, "p": PRODUCTION_NS}
    metadata = metadata_by_name(root)
    model_object = root.find("core:resources/core:object", ns)
    build = root.find("core:build", ns)
    build_item = root.find("core:build/core:item", ns)

    assert root.attrib["unit"] == "millimeter"
    assert metadata["Application"].startswith("BambuStudio-")
    assert metadata["BambuStudio:3mfVersion"] == "1"
    assert metadata["Title"] == "tiny & printable"
    assert model_object is not None
    assert re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        model_object.attrib[f"{{{PRODUCTION_NS}}}UUID"],
    )
    assert build is not None
    assert build.attrib[f"{{{PRODUCTION_NS}}}UUID"]
    assert build_item is not None
    assert build_item.attrib["transform"] == "1 0 0 0 1 0 0 0 1 128 128 0"


def test_bundle_metadata_contains_project_profiles_and_gui_safe_transform(tmp_path: Path):
    bundle_path = tmp_path / "metadata.3mf"

    write_bundle(
        bundle_path,
        mesh=tiny_tetrahedron(),
        object_name="fixture",
        profile_ids=profile_ids(),
        transform=GuiSafeTransform.bed_center(256, 256),
    )

    with zipfile.ZipFile(bundle_path) as archive:
        project_settings = json.loads(archive.read("Metadata/project_settings.config"))
        model_settings = ET.fromstring(archive.read("Metadata/model_settings.config"))
        slice_info = ET.fromstring(archive.read("Metadata/slice_info.config"))
        plate_thumbnail = archive.read("Metadata/plate_1.png")
        no_light_thumbnail = archive.read("Metadata/plate_no_light_1.png")

    assert project_settings["name"] == "project_settings"
    assert project_settings["from"] == "project"
    assert project_settings["version"] == "02.04.00.70"
    assert project_settings["filament_settings_id"] == ["Generic PLA"]
    assert project_settings["print_settings_id"] == "0.20mm Standard"
    assert project_settings["printer_settings_id"] == "Bambu Lab P2S 0.4 nozzle"
    assert project_settings["printer_model"] == "Bambu Lab P2S"
    assert project_settings["printer_variant"] == "0.4"
    assert project_settings["nozzle_diameter"] == ["0.4"]
    assert project_settings["printable_height"] == "256"

    metadata = {
        item.attrib["key"]: item.attrib["value"]
        for item in model_settings.findall(".//metadata")
    }
    transform_payload = json.loads(metadata["printpipe_transform"])
    assert metadata["matrix"] == "1 0 0 128 0 1 0 128 0 0 1 0 0 0 0 1"
    assert metadata["printpipe_transform_policy"] == "gui_safe_bed_center"
    assert transform_payload["translation_mm"] == [128.0, 128.0, 0.0]
    assert transform_payload["mesh_origin_policy"] == "origin_centered_z_dropped"
    assert transform_payload["applied_in"] == "model_settings_and_build_item"

    assert slice_info.find("./plate/object").attrib["name"] == "fixture"
    assert plate_thumbnail.startswith(b"\x89PNG\r\n\x1a\n")
    assert no_light_thumbnail == plate_thumbnail


def test_validate_bundle_accepts_written_bambu_bundle(tmp_path: Path):
    bundle_path = tmp_path / "valid.3mf"
    write_bundle(bundle_path, mesh=tiny_tetrahedron(), profile_ids=profile_ids())

    result = validate_bundle(bundle_path)

    assert result.ok
    assert result.errors == ()
    assert result.application == "BambuStudio-02.04.00.70"


def test_validate_bundle_reports_missing_required_members(tmp_path: Path):
    bundle_path = tmp_path / "missing.3mf"
    with zipfile.ZipFile(bundle_path, "w") as archive:
        archive.writestr("[Content_Types].xml", "")

    result = validate_bundle(bundle_path)

    assert not result.ok
    assert "missing archive member: 3D/3dmodel.model" in result.errors
    assert "missing archive member: Metadata/project_settings.config" in result.errors


def test_validate_bundle_reports_foreign_application_metadata(tmp_path: Path):
    bundle_path = tmp_path / "foreign.3mf"
    model = (
        f'<model xmlns="{CORE_NS}" unit="millimeter">'
        '<metadata name="Application">ForeignSlicer-1.0</metadata>'
        "</model>"
    )
    with zipfile.ZipFile(bundle_path, "w") as archive:
        for member in REQUIRED_MEMBERS:
            archive.writestr(member, model if member == "3D/3dmodel.model" else "")

    result = validate_bundle(bundle_path)

    assert not result.ok
    assert (
        "Application metadata must start with BambuStudio-; found ForeignSlicer-1.0"
        in result.errors
    )


def test_model_xml_builder_requires_bambu_application_prefix():
    with pytest.raises(ValueError, match="application must start with BambuStudio-"):
        build_model_xml(tiny_tetrahedron(), application="ForeignSlicer-1.0")
