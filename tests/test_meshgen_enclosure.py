"""Track A: parametric enclosure generator produces watertight, dimensioned, sliceable geometry."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("trimesh")  # enclosure primitive needs the optional trimesh dependency

from printpipe.contracts import ArtifactKind, InputKind, StageStatus
from printpipe.geometry.artifacts import _read_ascii_stl_triangles
from printpipe.meshgen.contracts import MeshGenRequest
from printpipe.meshgen.enclosure import Cutout, EnclosureSpec, build_enclosure
from printpipe.meshgen.parametric_cad import ParametricCadProvider
from printpipe.runs.paths import create_prompt_run

_HOLES = ((29.0, 11.5), (29.0, -11.5), (-29.0, 11.5), (-29.0, -11.5))


def _spec(**overrides) -> EnclosureSpec:
    base = dict(
        board_length_mm=65.0,
        board_width_mm=30.0,
        internal_height_mm=14.0,
        mount_holes_xy=_HOLES,
    )
    base.update(overrides)
    return EnclosureSpec(**base)


def test_enclosure_is_watertight_manifold_and_correctly_sized() -> None:
    mesh = build_enclosure(_spec())
    assert mesh.is_watertight
    assert mesh.is_winding_consistent
    assert mesh.volume > 0
    extents = mesh.extents
    assert abs(extents[0] - 70.2) < 0.2  # 65 + 2*clearance + 2*wall
    assert abs(extents[1] - 35.2) < 0.2  # 30 + 2*clearance + 2*wall
    assert abs(extents[2] - 15.6) < 0.2  # floor + internal_height
    assert abs(mesh.bounds[0][2]) < 1e-6  # base sits on the bed (z=0)


def test_cutout_removes_material_through_the_wall() -> None:
    solid = build_enclosure(_spec(cutouts=()))
    holed = build_enclosure(
        _spec(cutouts=(Cutout(face="-y", u_mm=-10.0, z_center_mm=6.0, width_mm=9.0, height_mm=4.0),))
    )
    assert holed.is_watertight
    assert holed.volume < solid.volume  # the micro-USB opening removed material


def test_provider_enclosure_primitive_writes_parseable_ascii_stl(tmp_path: Path) -> None:
    layout = create_prompt_run("pi zero 2w tray", tmp_path / "runs", run_id="r-enc")
    request = MeshGenRequest(
        input_kind=InputKind.PROMPT,
        source_paths=(),
        output_formats=("stl",),
        provider_params={
            "primitive": "enclosure",
            "enclosure": {
                "board_length_mm": 65,
                "board_width_mm": 30,
                "mount_holes_xy": [[29, 11.5], [29, -11.5], [-29, 11.5], [-29, -11.5]],
                "cutouts": [{"face": "-y", "u_mm": -10, "z_center_mm": 6.0, "width_mm": 9, "height_mm": 4}],
                "name": "pi_zero_2w_tray",
            },
        },
        max_attempts=1,
    )
    result = ParametricCadProvider().generate(request, layout)

    assert result.status == StageStatus.SUCCEEDED
    assert result.artifact is not None
    assert result.artifact.kind == ArtifactKind.GENERATED_MESH
    assert result.artifact.metadata["primitive"] == "enclosure"
    assert result.artifact.metadata["board_mm"] == [65.0, 30.0]

    stl_path = Path(result.artifact.path)
    assert stl_path.name.endswith("_enclosure.stl")
    assert b"\x00" not in stl_path.read_bytes()  # ASCII, not binary
    triangles = _read_ascii_stl_triangles(stl_path)  # PrintPipe's own reader accepts it
    assert len(triangles) > 100  # a real enclosure, not the 12-triangle box


def test_faceplate_is_watertight_with_lens_and_screw_holes() -> None:
    from printpipe.meshgen.enclosure import FaceplateSpec, build_faceplate

    holes = ((15.0, 15.0), (15.0, -15.0), (-15.0, 15.0), (-15.0, -15.0))
    plate = build_faceplate(
        FaceplateSpec(length_mm=46, width_mm=46, thickness_mm=3, lens_hole_dia_mm=40, mount_holes_xy=holes)
    )
    assert plate.is_watertight
    assert plate.is_winding_consistent
    ext = plate.extents
    assert abs(ext[0] - 46) < 0.2 and abs(ext[1] - 46) < 0.2 and abs(ext[2] - 3) < 0.2

    lens_only = build_faceplate(
        FaceplateSpec(length_mm=46, width_mm=46, thickness_mm=3, lens_hole_dia_mm=40, mount_holes_xy=())
    )
    assert plate.volume < lens_only.volume  # the 4 screw holes removed extra material


def test_tripod_mount_stays_watertight_and_adds_boss() -> None:
    from printpipe.meshgen.enclosure import TripodMount

    without = build_enclosure(_spec(standoff_height_mm=10.0))
    with_mount = build_enclosure(_spec(standoff_height_mm=10.0, tripod_mount=TripodMount()))
    assert with_mount.is_watertight
    assert with_mount.is_winding_consistent
    # The boss adds more material than the nut pocket + screw hole remove (feature applied,
    # and the pocket/hole booleans kept the mesh manifold).
    assert with_mount.volume > without.volume


def test_lid_bosses_and_lid_plate_close_the_enclosure() -> None:
    from printpipe.meshgen.enclosure import LidSpec, build_lid

    bosses = ((25.0, 10.0), (25.0, -10.0), (-25.0, 10.0), (-25.0, -10.0))
    spec = _spec(standoff_height_mm=6.0, lid=LidSpec(boss_xy=bosses))
    body = build_enclosure(spec)
    lid = build_lid(spec)

    assert body.is_watertight and body.is_winding_consistent
    assert lid.is_watertight and lid.is_winding_consistent
    # lid footprint matches the body outer footprint
    assert abs(lid.extents[0] - spec.outer_length_mm) < 0.2
    assert abs(lid.extents[1] - spec.outer_width_mm) < 0.2
    # the lid has screw clearance holes -> less material than a hole-less plate
    solid_lid = build_lid(_spec(standoff_height_mm=6.0, lid=LidSpec(boss_xy=())))
    assert lid.volume < solid_lid.volume
