from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest

from printpipe.bambu.threemf import (
    CORE_NS,
    BambuProfileIds,
    GuiSafeTransform,
    MeshGeometry,
    validate_bundle,
)
from printpipe.bambu.threemf.mesh_adapter import read_ascii_stl, write_bundle_from_ascii_stl


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


def write_tiny_ascii_stl(path: Path) -> None:
    path.write_text(
        """solid tiny
  facet normal 0 0 1
    outer loop
      vertex 0 0 0
      vertex 10 0 0
      vertex 0 10 0
    endloop
  endfacet
  facet normal 1 0 0
    outer loop
      vertex 0 0 0
      vertex 0 10 0
      vertex 0 0 10
    endloop
  endfacet
endsolid tiny
""",
        encoding="ascii",
    )


def test_read_ascii_stl_converts_triangles_to_mesh_geometry(tmp_path: Path):
    stl_path = tmp_path / "tiny.stl"
    write_tiny_ascii_stl(stl_path)

    mesh = read_ascii_stl(stl_path)

    assert isinstance(mesh, MeshGeometry)
    assert mesh.vertices == (
        (0.0, 0.0, 0.0),
        (10.0, 0.0, 0.0),
        (0.0, 10.0, 0.0),
        (0.0, 0.0, 10.0),
    )
    assert mesh.triangles == ((0, 1, 2), (0, 2, 3))


def test_write_bundle_from_ascii_stl_writes_validator_clean_bundle(tmp_path: Path):
    stl_path = tmp_path / "tiny.stl"
    bundle_path = tmp_path / "tiny.3mf"
    write_tiny_ascii_stl(stl_path)

    written = write_bundle_from_ascii_stl(
        stl_path,
        bundle_path,
        profile_ids(),
        "adapter object",
        GuiSafeTransform.bed_center(200, 180),
    )

    result = validate_bundle(written)

    assert written == bundle_path
    assert result.ok
    assert result.application == "BambuStudio-02.04.00.70"

    with zipfile.ZipFile(bundle_path) as archive:
        model = ET.fromstring(archive.read("3D/3dmodel.model"))

    ns = {"core": CORE_NS}
    vertices = model.findall(".//core:vertex", ns)
    triangles = model.findall(".//core:triangle", ns)
    build_item = model.find("core:build/core:item", ns)

    assert len(vertices) == 4
    assert len(triangles) == 2
    assert build_item is not None
    assert build_item.attrib["transform"] == "1 0 0 0 1 0 0 0 1 100 90 0"


def test_read_ascii_stl_rejects_binary_stl(tmp_path: Path):
    stl_path = tmp_path / "binary.stl"
    stl_path.write_bytes(b"\0not an ascii stl")

    with pytest.raises(ValueError, match="binary STL is not supported"):
        read_ascii_stl(stl_path)


def test_read_ascii_stl_rejects_non_triangular_facets(tmp_path: Path):
    stl_path = tmp_path / "bad.stl"
    stl_path.write_text(
        """solid bad
  facet normal 0 0 1
    outer loop
      vertex 0 0 0
      vertex 1 0 0
    endloop
  endfacet
endsolid bad
""",
        encoding="ascii",
    )

    with pytest.raises(ValueError, match="facet must contain exactly 3 vertices"):
        read_ascii_stl(stl_path)
