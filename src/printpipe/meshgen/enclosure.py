"""Parametric enclosure generator (Track A) — watertight by construction via trimesh CSG.

This is the real code-CAD upgrade over the Stage-0 box primitive: it builds a
tray-style enclosure (walls + floor + screw standoffs + parameterized side
cutouts + optional lens hole) using boolean operations, so the output is a
single watertight, manifold solid with dimensioned openings — exactly what a
functional electronics enclosure needs and what AI mesh-gen cannot produce.

Requires ``trimesh`` (an optional PrintPipe dependency). Importing this module
without trimesh raises ImportError; the box primitive in ``parametric_cad`` stays
dependency-free and is unaffected.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import trimesh
from trimesh.exchange.stl import export_stl_ascii

Face = Literal["+x", "-x", "+y", "-y"]


@dataclass(frozen=True)
class Cutout:
    """A rectangular opening punched through one wall (e.g. a micro-USB port)."""

    face: Face
    u_mm: float          # offset along the wall from board centre (signed)
    z_center_mm: float   # vertical centre of the opening above the floor exterior
    width_mm: float      # opening size along the wall
    height_mm: float     # opening size vertically


@dataclass(frozen=True)
class FloorCutout:
    """A rectangular opening through the floor (e.g. for an external bracket to pass through)."""

    x_mm: float = 0.0
    y_mm: float = 0.0
    size_x_mm: float = 20.0  # along the case depth (X)
    size_y_mm: float = 20.0  # along the case width (Y)


@dataclass(frozen=True)
class LensHole:
    """A round opening (cutout) through the floor or a wall for a lens/cable."""

    face: Literal["floor", "+x", "-x", "+y", "-y"]
    u_mm: float
    v_mm: float
    diameter_mm: float
    collar_outer_dia_mm: float = 0.0   # >0 adds a raised ring on the +x outer face (camera look)
    collar_height_mm: float = 0.0      # how far the collar projects past the wall


@dataclass(frozen=True)
class TripodMount:
    """A 1/4-20 tripod socket on the case bottom: a solid boss with a self-tapping pilot hole.

    The tripod's steel 1/4-20 male screw threads directly into the boss, cutting its own
    thread. FDM-printed fine threads (1.27mm pitch) are weak/rough, so a steel screw
    self-tapping into a slightly undersized hole holds far better. Tune ``pilot_dia_mm``
    for your screw/material (smaller = tighter bite). The hole is blind, so the cavity
    stays sealed from below. The Pi must sit on standoffs tall enough to clear the boss.
    """

    x_mm: float = 0.0
    y_mm: float = 0.0
    major_dia_mm: float = 6.35     # 1/4-20 major diameter
    pitch_mm: float = 1.27         # 20 TPI
    thread_depth_mm: float = 8.0   # depth of the threaded socket
    clearance_mm: float = 0.25     # radial clearance so the steel screw spins in (FDM fit)
    boss_dia_mm: float = 14.0
    boss_height_mm: float = 9.0    # internal boss above the floor (gives thread depth)


@dataclass(frozen=True)
class CameraMount:
    """Standoff posts on the front (+x) inner wall that the HQ camera board bolts to.

    Holds the board parallel to the front wall, centred at ``v_center_mm`` so the lens lines
    up with the lens hole, and lifted so the CSI ribbon (which exits the board's bottom edge)
    has clearance to the floor below it.
    """

    v_center_mm: float = 27.0     # optical-axis height above the floor
    pitch_mm: float = 30.0        # M2.5 hole pattern on the IMX477 (30x30)
    post_len_mm: float = 5.0      # how far the board stands off the inner wall
    post_dia_mm: float = 6.0
    pilot_dia_mm: float = 2.1     # M2.5 self-tap


@dataclass(frozen=True)
class LidSpec:
    """A flat screw-down lid: full-height corner bosses in the body + a matching plate.

    The body gets vertical bosses at ``boss_xy`` with blind self-tap pilot holes from the
    top; the lid is a flat plate with matching clearance holes, fastened with screws.
    """

    thickness_mm: float = 2.4
    boss_dia_mm: float = 7.0
    boss_pilot_dia_mm: float = 2.5       # M3 self-tap into the boss
    screw_clearance_dia_mm: float = 3.4  # clearance through the lid plate
    pilot_depth_mm: float = 9.0
    boss_xy: tuple[tuple[float, float], ...] = ()


@dataclass(frozen=True)
class EnclosureSpec:
    board_length_mm: float
    board_width_mm: float
    internal_height_mm: float = 14.0
    wall_mm: float = 2.0
    floor_mm: float = 1.6
    clearance_mm: float = 0.6
    mount_holes_xy: tuple[tuple[float, float], ...] = ()  # relative to board centre
    standoff_height_mm: float = 3.0
    standoff_outer_dia_mm: float = 6.0
    screw_hole_dia_mm: float = 2.2  # M2.5 self-tap pilot
    cutouts: tuple[Cutout, ...] = ()
    lens_holes: tuple[LensHole, ...] = ()
    floor_cutouts: tuple[FloorCutout, ...] = ()
    tripod_mount: TripodMount | None = None
    camera_mount: CameraMount | None = None
    lid: LidSpec | None = None
    name: str = "enclosure"

    @property
    def inner_length_mm(self) -> float:
        return self.board_length_mm + 2 * self.clearance_mm

    @property
    def inner_width_mm(self) -> float:
        return self.board_width_mm + 2 * self.clearance_mm

    @property
    def outer_length_mm(self) -> float:
        return self.inner_length_mm + 2 * self.wall_mm

    @property
    def outer_width_mm(self) -> float:
        return self.inner_width_mm + 2 * self.wall_mm

    @property
    def total_height_mm(self) -> float:
        return self.floor_mm + self.internal_height_mm


def _box(extents: tuple[float, float, float], center: tuple[float, float, float]) -> trimesh.Trimesh:
    mesh = trimesh.creation.box(extents=list(extents))
    mesh.apply_translation(list(center))
    return mesh


def _zcyl(radius: float, height: float, center: tuple[float, float, float]) -> trimesh.Trimesh:
    """A Z-axis cylinder centred at ``center``."""
    mesh = trimesh.creation.cylinder(radius=radius, height=height, sections=64)
    mesh.apply_translation(list(center))
    return mesh


def _cutout_solid(spec: EnclosureSpec, cut: Cutout) -> trimesh.Trimesh:
    through = spec.wall_mm + 2.0  # span fully across the wall
    if cut.face in ("+y", "-y"):
        sign = 1.0 if cut.face == "+y" else -1.0
        y = sign * (spec.inner_width_mm / 2 + spec.wall_mm / 2)
        return _box((cut.width_mm, through, cut.height_mm), (cut.u_mm, y, cut.z_center_mm))
    sign = 1.0 if cut.face == "+x" else -1.0
    x = sign * (spec.inner_length_mm / 2 + spec.wall_mm / 2)
    return _box((through, cut.width_mm, cut.height_mm), (x, cut.u_mm, cut.z_center_mm))


def _threaded_cutter(
    *,
    major_dia_mm: float,
    pitch_mm: float,
    depth_mm: float,
    x_mm: float,
    y_mm: float,
    clearance_mm: float,
    ang_steps: int = 64,
    steps_per_pitch: int = 24,
) -> trimesh.Trimesh:
    """A watertight helical 'screw' solid; subtract it from a boss to cut an internal thread.

    Built as a single-valued radial height-field on a cylinder (radius varies with angle and
    height to form the V-ridge), so it is guaranteed manifold with no self-intersection.
    """

    r_major = major_dia_mm / 2.0 + clearance_mm
    r_minor = max(0.6, r_major - 0.61 * pitch_mm)  # UN thread radial depth ~= 0.61*pitch
    z0 = -1.0
    length = depth_mm + 1.0  # start below the bed so the bottom is cut cleanly
    n_z = max(8, int(round(length / pitch_mm * steps_per_pitch)) + 1)
    zs = np.linspace(0.0, length, n_z)
    thetas = np.linspace(0.0, 2.0 * np.pi, ang_steps, endpoint=False)
    cos_t, sin_t = np.cos(thetas), np.sin(thetas)

    verts: list[tuple[float, float, float]] = []
    for z in zs:
        frac = (z - (thetas / (2.0 * np.pi)) * pitch_mm) / pitch_mm
        frac = frac - np.floor(frac)
        ridge = 1.0 - np.abs(2.0 * frac - 1.0)  # 0 at valley .. 1 at crest
        r = r_minor + (r_major - r_minor) * ridge
        xs = x_mm + r * cos_t
        ys = y_mm + r * sin_t
        for j in range(ang_steps):
            verts.append((float(xs[j]), float(ys[j]), float(z0 + z)))

    faces: list[tuple[int, int, int]] = []
    a = ang_steps
    for zi in range(n_z - 1):
        base, nxt = zi * a, (zi + 1) * a
        for j in range(a):
            j2 = (j + 1) % a
            faces.append((base + j, base + j2, nxt + j2))
            faces.append((base + j, nxt + j2, nxt + j))
    bottom_c = len(verts)
    verts.append((x_mm, y_mm, float(z0 + zs[0])))
    top_c = len(verts)
    verts.append((x_mm, y_mm, float(z0 + zs[-1])))
    base_top = (n_z - 1) * a
    for j in range(a):
        j2 = (j + 1) % a
        faces.append((bottom_c, j2, j))
        faces.append((top_c, base_top + j, base_top + j2))

    mesh = trimesh.Trimesh(vertices=np.array(verts), faces=np.array(faces), process=False)
    if mesh.volume < 0:  # ensure outward winding without scipy-backed fix_normals
        mesh.invert()
    return mesh


def _lens_solid(spec: EnclosureSpec, hole: LensHole) -> trimesh.Trimesh:
    if hole.face == "floor":
        return _zcyl(hole.diameter_mm / 2, spec.floor_mm + 2.0, (hole.u_mm, hole.v_mm, spec.floor_mm / 2))
    collar = hole.collar_height_mm if hole.face == "+x" else 0.0
    through = spec.wall_mm + 2.0 + collar
    cyl = trimesh.creation.cylinder(radius=hole.diameter_mm / 2, height=through, sections=64)
    if hole.face in ("+y", "-y"):
        cyl.apply_transform(trimesh.transformations.rotation_matrix(3.14159265358979 / 2, [1, 0, 0]))
        sign = 1.0 if hole.face == "+y" else -1.0
        cyl.apply_translation([hole.u_mm, sign * (spec.inner_width_mm / 2 + spec.wall_mm / 2), hole.v_mm])
    else:
        cyl.apply_transform(trimesh.transformations.rotation_matrix(3.14159265358979 / 2, [0, 1, 0]))
        sign = 1.0 if hole.face == "+x" else -1.0
        # shift outward by collar/2 so the cut spans wall + collar
        x_center = sign * (spec.inner_length_mm / 2 + spec.wall_mm / 2 + collar / 2)
        cyl.apply_translation([x_center, hole.u_mm, hole.v_mm])
    return cyl


def build_enclosure(spec: EnclosureSpec) -> trimesh.Trimesh:
    """Build a watertight tray enclosure as a single trimesh solid."""

    total_h = spec.total_height_mm
    outer = _box(
        (spec.outer_length_mm, spec.outer_width_mm, total_h),
        (0.0, 0.0, total_h / 2),
    )
    cavity_h = spec.internal_height_mm + 2.0
    cavity = _box(
        (spec.inner_length_mm, spec.inner_width_mm, cavity_h),
        (0.0, 0.0, spec.floor_mm + cavity_h / 2),
    )
    tray = outer.difference(cavity)

    # Standoffs rise from the floor; overlap the floor slightly for a solid weld.
    posts = []
    for x, y in spec.mount_holes_xy:
        h = spec.standoff_height_mm + 0.5
        posts.append(_zcyl(spec.standoff_outer_dia_mm / 2, h, (x, y, spec.floor_mm - 0.5 + h / 2)))
    # Tripod boss: a solid pillar from the bed up, to house the captured nut.
    if spec.tripod_mount is not None:
        tm = spec.tripod_mount
        boss_h = spec.floor_mm + tm.boss_height_mm
        posts.append(_zcyl(tm.boss_dia_mm / 2, boss_h, (tm.x_mm, tm.y_mm, boss_h / 2)))
    # Lid bosses: full-height corner columns the lid screws into.
    if spec.lid is not None:
        for bx, by in spec.lid.boss_xy:
            posts.append(_zcyl(spec.lid.boss_dia_mm / 2, spec.total_height_mm, (bx, by, spec.total_height_mm / 2)))
    # Camera standoffs: posts projecting inward (-x) from the front wall; board bolts here,
    # held at v_center so the ribbon (board's bottom edge) clears the floor below.
    if spec.camera_mount is not None:
        cm = spec.camera_mount
        x_front = spec.inner_length_mm / 2
        half = cm.pitch_mm / 2
        plen = cm.post_len_mm + 0.5
        for dy in (-half, half):
            for dz in (-half, half):
                post = trimesh.creation.cylinder(radius=cm.post_dia_mm / 2, height=plen, sections=32)
                post.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [0, 1, 0]))
                post.apply_translation([x_front - plen / 2 + 0.25, dy, cm.v_center_mm + dz])
                posts.append(post)
    # Raised lens collar(s): a ring on the +x outer face (the camera look).
    for h in spec.lens_holes:
        if h.collar_outer_dia_mm > 0 and h.face == "+x":
            x_out = spec.inner_length_mm / 2 + spec.wall_mm
            clen = h.collar_height_mm + 0.5
            col = trimesh.creation.cylinder(radius=h.collar_outer_dia_mm / 2, height=clen, sections=64)
            col.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [0, 1, 0]))
            col.apply_translation([x_out + h.collar_height_mm / 2 - 0.25, h.u_mm, h.v_mm])
            posts.append(col)
    if posts:
        tray = trimesh.boolean.union([tray, *posts])

    # Cuts: screw pilot holes (blind, into posts), side cutouts, lens holes.
    cuts = []
    for x, y in spec.mount_holes_xy:
        cuts.append(_zcyl(spec.screw_hole_dia_mm / 2, spec.standoff_height_mm, (x, y, spec.floor_mm + spec.standoff_height_mm / 2)))
    cuts.extend(_cutout_solid(spec, c) for c in spec.cutouts)
    cuts.extend(_lens_solid(spec, h) for h in spec.lens_holes)
    # Camera mount pilots: M2.5 self-tap, blind into each front post from the camera side.
    if spec.camera_mount is not None:
        cm = spec.camera_mount
        x_front = spec.inner_length_mm / 2
        half = cm.pitch_mm / 2
        for dy in (-half, half):
            for dz in (-half, half):
                pil = trimesh.creation.cylinder(radius=cm.pilot_dia_mm / 2, height=cm.post_len_mm, sections=24)
                pil.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [0, 1, 0]))
                pil.apply_translation([x_front - cm.post_len_mm / 2, dy, cm.v_center_mm + dz])
                cuts.append(pil)
    for fc in spec.floor_cutouts:
        cuts.append(_box((fc.size_x_mm, fc.size_y_mm, spec.floor_mm + 2.0), (fc.x_mm, fc.y_mm, spec.floor_mm / 2)))
    if spec.lid is not None:
        for bx, by in spec.lid.boss_xy:
            cuts.append(_zcyl(spec.lid.boss_pilot_dia_mm / 2, spec.lid.pilot_depth_mm, (bx, by, spec.total_height_mm - spec.lid.pilot_depth_mm / 2)))
    if cuts:
        tray = tray.difference(trimesh.boolean.union(cuts) if len(cuts) > 1 else cuts[0])

    # Threaded tripod socket: cut as its own boolean to keep the complex helix isolated.
    if spec.tripod_mount is not None:
        tm = spec.tripod_mount
        tray = tray.difference(
            _threaded_cutter(
                major_dia_mm=tm.major_dia_mm,
                pitch_mm=tm.pitch_mm,
                depth_mm=tm.thread_depth_mm,
                x_mm=tm.x_mm,
                y_mm=tm.y_mm,
                clearance_mm=tm.clearance_mm,
            )
        )

    tray.merge_vertices()
    return tray


def enclosure_ascii_stl(spec: EnclosureSpec) -> str:
    """Return the enclosure as ASCII STL text (the only mesh format PrintPipe reads)."""
    return export_stl_ascii(build_enclosure(spec))


def build_lid(spec: EnclosureSpec) -> trimesh.Trimesh:
    """A flat lid plate matching the enclosure footprint, with screw clearance holes."""

    if spec.lid is None:
        raise ValueError("build_lid requires spec.lid")
    t = spec.lid.thickness_mm
    plate = _box((spec.outer_length_mm, spec.outer_width_mm, t), (0.0, 0.0, t / 2))
    cuts = [
        _zcyl(spec.lid.screw_clearance_dia_mm / 2, t + 2.0, (bx, by, t / 2))
        for bx, by in spec.lid.boss_xy
    ]
    if cuts:
        plate = plate.difference(trimesh.boolean.union(cuts) if len(cuts) > 1 else cuts[0])
    plate.merge_vertices()
    return plate


def lid_ascii_stl(spec: EnclosureSpec) -> str:
    return export_stl_ascii(build_lid(spec))


@dataclass(frozen=True)
class FaceplateSpec:
    """A flat mounting plate with a central round opening and corner screw holes.

    Used for the camera face: the HQ camera bolts to it on its 30x30 M2.5 pattern,
    the lens passes through the central hole.
    """

    length_mm: float
    width_mm: float
    thickness_mm: float = 3.0
    lens_hole_dia_mm: float = 40.0
    lens_center_xy: tuple[float, float] = (0.0, 0.0)
    mount_holes_xy: tuple[tuple[float, float], ...] = ()
    mount_hole_dia_mm: float = 2.75
    name: str = "faceplate"


def build_faceplate(spec: FaceplateSpec) -> trimesh.Trimesh:
    """Build a watertight flat faceplate with a lens hole and corner screw holes."""

    t = spec.thickness_mm
    plate = _box((spec.length_mm, spec.width_mm, t), (0.0, 0.0, t / 2))
    cuts = [_zcyl(spec.lens_hole_dia_mm / 2, t + 2.0, (spec.lens_center_xy[0], spec.lens_center_xy[1], t / 2))]
    for x, y in spec.mount_holes_xy:
        cuts.append(_zcyl(spec.mount_hole_dia_mm / 2, t + 2.0, (x, y, t / 2)))
    plate = plate.difference(trimesh.boolean.union(cuts) if len(cuts) > 1 else cuts[0])
    plate.merge_vertices()
    return plate


def faceplate_ascii_stl(spec: FaceplateSpec) -> str:
    return export_stl_ascii(build_faceplate(spec))


@dataclass(frozen=True)
class GripSpec:
    """A bail / suitcase hand grip: a graspable bar held off the wall by two end legs.

    Legs only at the two ends; the bar is open on every other side, so a hand wraps it.
    Mounts to a side wall via a self-tap hole in each leg foot (screws driven from inside
    the body). The clear span between the legs fits a hand; the standoff is the finger gap.
    """

    mount_span_mm: float = 110.0   # centre-to-centre of the two legs (= body mount-hole spacing)
    standoff_mm: float = 45.0      # how far the bar stands off the wall (finger wrap + clearance)
    bar_mm: float = 16.0           # round grip-bar diameter (slimmer + rounded = easier to hold)
    leg_mm: float = 14.0           # leg thickness along the body axis
    mount_hole_dia_mm: float = 4.0  # ø4.0 pocket for an M3 heat-set insert (screw from the body wall)
    name: str = "grip"


def build_grip(spec: GripSpec) -> trimesh.Trimesh:
    """Build a watertight bail handle: two end legs + a grip bar, with a hole in each foot."""

    span, S, bar, leg = spec.mount_span_mm, spec.standoff_mm, spec.bar_mm, spec.leg_mm
    # Frame: x along the body (legs at x=0 and x=span), y = standoff off the wall (0..S),
    # z = bar thickness (0..bar). The wall is NOT part of the grip — it's fully open.
    # Fully round bail: round legs (cylinders along the standoff axis Y) + a round bar.
    # Each leg's flat end-cap (y=0) seats against the wall and holds the insert pocket.
    rot_y = trimesh.transformations.rotation_matrix(math.pi / 2, [1, 0, 0])  # Z -> Y
    leg_a = trimesh.creation.cylinder(radius=bar / 2, height=S, sections=48)
    leg_a.apply_transform(rot_y)
    leg_a.apply_translation([0.0, S / 2, bar / 2])
    leg_b = trimesh.creation.cylinder(radius=bar / 2, height=S, sections=48)
    leg_b.apply_transform(rot_y)
    leg_b.apply_translation([span, S / 2, bar / 2])
    # Round grip bar (cylinder along X) capping the leg tops.
    grip_bar = trimesh.creation.cylinder(radius=bar / 2, height=span + bar, sections=48)
    grip_bar.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [0, 1, 0]))
    grip_bar.apply_translation([span / 2, S - bar / 2, bar / 2])
    grip = trimesh.boolean.union([leg_a, leg_b, grip_bar])

    # Heat-set insert pocket in each leg foot; the M3 screw comes from inside the body wall.
    pockets = []
    for x_center in (0.0, span):
        cyl = trimesh.creation.cylinder(radius=spec.mount_hole_dia_mm / 2, height=7.0, sections=32)
        cyl.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [1, 0, 0]))
        cyl.apply_translation([x_center, 3.5, bar / 2])  # opens at the wall foot (y=0), 7 mm deep
        pockets.append(cyl)
    grip = grip.difference(trimesh.boolean.union(pockets))
    grip.merge_vertices()
    return grip


def grip_ascii_stl(spec: GripSpec) -> str:
    return export_stl_ascii(build_grip(spec))


__all__ = [
    "EnclosureSpec",
    "Cutout",
    "FloorCutout",
    "LensHole",
    "TripodMount",
    "CameraMount",
    "LidSpec",
    "FaceplateSpec",
    "GripSpec",
    "build_enclosure",
    "enclosure_ascii_stl",
    "build_lid",
    "lid_ascii_stl",
    "build_grip",
    "grip_ascii_stl",
    "build_faceplate",
    "faceplate_ascii_stl",
]
