"""Parametric code-CAD mesh provider (Stage 0 kill-switch primitive).

Generates print-clean geometry *programmatically* — no imported mesh and no AI
mesh-generation service — and writes it as ASCII STL into the run meshgen
directory, so it flows through the existing repair -> orient -> bundle -> slice
spine like any other generated mesh.

Stage 0 ships a built-in parametric *box* primitive with ZERO third-party
dependencies, to prove the code-CAD -> clean-STL -> slice path end to end. A real
CAD kernel (cadquery / build123d) plugs in behind ``_build_box_triangles`` in a
later wave without changing this provider's contract: the output is already
watertight, manifold, and dimensioned by construction, which is exactly what the
fragile AI-mesh-repair path cannot guarantee.
"""

from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Any

from printpipe.contracts import Artifact, ArtifactKind, InputKind, StageStatus
from printpipe.runs.paths import RunLayout

from .contracts import (
    DeleteResult,
    MeshGenCapabilities,
    MeshGenCost,
    MeshGenEstimate,
    MeshGenRequest,
    MeshGenResult,
    MeshGenTiming,
    ProviderHealth,
)
from .providers import sha256_file, utc_now, write_provider_receipts

# A small flex-coupon footprint: prints fast, fits any Bambu bed, exercises the
# whole spine. Override via request.provider_params["box_mm"] = [L, W, H].
DEFAULT_BOX_MM: tuple[float, float, float] = (40.0, 15.0, 3.0)

# 8 corners of an axis-aligned box anchored at the origin, in a fixed index order.
#   0:(0,0,0) 1:(L,0,0) 2:(L,W,0) 3:(0,W,0)   bottom (z=0)
#   4:(0,0,H) 5:(L,0,H) 6:(L,W,H) 7:(0,W,H)   top    (z=H)
# 12 triangles wound counter-clockwise as seen from OUTSIDE, so each face normal
# points outward (verified by right-hand rule below).
_BOX_FACES: tuple[tuple[int, int, int], ...] = (
    (0, 2, 1), (0, 3, 2),  # bottom  -Z
    (4, 5, 6), (4, 6, 7),  # top     +Z
    (0, 1, 5), (0, 5, 4),  # front   -Y
    (3, 6, 2), (3, 7, 6),  # back    +Y
    (0, 4, 7), (0, 7, 3),  # left    -X
    (1, 2, 6), (1, 6, 5),  # right   +X
)


def _box_corners(length: float, width: float, height: float) -> tuple[tuple[float, float, float], ...]:
    return (
        (0.0, 0.0, 0.0),
        (length, 0.0, 0.0),
        (length, width, 0.0),
        (0.0, width, 0.0),
        (0.0, 0.0, height),
        (length, 0.0, height),
        (length, width, height),
        (0.0, width, height),
    )


def _build_box_triangles(
    dimensions_mm: tuple[float, float, float],
) -> tuple[tuple[tuple[float, float, float], ...], ...]:
    """Return the 12 outward-wound triangles of a watertight box."""

    corners = _box_corners(*dimensions_mm)
    return tuple(tuple(corners[index] for index in face) for face in _BOX_FACES)


def _unit_normal(triangle: tuple[tuple[float, float, float], ...]) -> tuple[float, float, float]:
    (ax, ay, az), (bx, by, bz), (cx, cy, cz) = triangle
    ux, uy, uz = bx - ax, by - ay, bz - az
    vx, vy, vz = cx - ax, cy - ay, cz - az
    nx = (uy * vz) - (uz * vy)
    ny = (uz * vx) - (ux * vz)
    nz = (ux * vy) - (uy * vx)
    length = math.sqrt((nx * nx) + (ny * ny) + (nz * nz))
    if length == 0.0:
        return (0.0, 0.0, 0.0)
    return (nx / length, ny / length, nz / length)


def _write_ascii_stl(
    output_path: Path,
    solid_name: str,
    triangles: tuple[tuple[tuple[float, float, float], ...], ...],
) -> None:
    lines = [f"solid {solid_name}"]
    for triangle in triangles:
        nx, ny, nz = _unit_normal(triangle)
        lines.append(f"  facet normal {nx:.6g} {ny:.6g} {nz:.6g}")
        lines.append("    outer loop")
        for x, y, z in triangle:
            lines.append(f"      vertex {x:.6g} {y:.6g} {z:.6g}")
        lines.append("    endloop")
        lines.append("  endfacet")
    lines.append(f"endsolid {solid_name}")
    lines.append("")
    output_path.write_text("\n".join(lines), encoding="ascii")


def _resolve_box_mm(request: MeshGenRequest) -> tuple[float, float, float]:
    raw = request.provider_params.get("box_mm")
    if raw is None:
        return DEFAULT_BOX_MM
    try:
        length, width, height = (float(value) for value in raw)
    except (TypeError, ValueError):
        return DEFAULT_BOX_MM
    if length <= 0 or width <= 0 or height <= 0:
        return DEFAULT_BOX_MM
    return (length, width, height)


def _enclosure_spec_from_params(params: dict[str, Any]):
    """Parse a provider 'enclosure' params dict into an EnclosureSpec (used by body and lid)."""

    from printpipe.meshgen.enclosure import (
        CameraMount,
        Cutout,
        EnclosureSpec,
        FloorCutout,
        LensHole,
        LidSpec,
        TripodMount,
    )

    p = dict(params)
    cutouts = tuple(Cutout(**cut) for cut in p.pop("cutouts", []) or [])
    lens_holes = tuple(LensHole(**hole) for hole in p.pop("lens_holes", []) or [])
    floor_cutouts = tuple(FloorCutout(**fc) for fc in p.pop("floor_cutouts", []) or [])
    mount_holes = tuple((float(x), float(y)) for x, y in p.pop("mount_holes_xy", []) or [])
    tripod_raw = p.pop("tripod_mount", None)
    tripod_mount = TripodMount(**tripod_raw) if isinstance(tripod_raw, dict) else None
    camera_raw = p.pop("camera_mount", None)
    camera_mount = CameraMount(**camera_raw) if isinstance(camera_raw, dict) else None
    lid_raw = p.pop("lid", None)
    if isinstance(lid_raw, dict):
        lid_kw = dict(lid_raw)
        boss_xy = tuple((float(x), float(y)) for x, y in lid_kw.pop("boss_xy", []) or [])
        lid = LidSpec(boss_xy=boss_xy, **lid_kw)
    else:
        lid = None
    return EnclosureSpec(
        board_length_mm=float(p.get("board_length_mm", 65.0)),
        board_width_mm=float(p.get("board_width_mm", 30.0)),
        internal_height_mm=float(p.get("internal_height_mm", 14.0)),
        wall_mm=float(p.get("wall_mm", 2.0)),
        floor_mm=float(p.get("floor_mm", 1.6)),
        clearance_mm=float(p.get("clearance_mm", 0.6)),
        mount_holes_xy=mount_holes,
        standoff_height_mm=float(p.get("standoff_height_mm", 3.0)),
        standoff_outer_dia_mm=float(p.get("standoff_outer_dia_mm", 6.0)),
        screw_hole_dia_mm=float(p.get("screw_hole_dia_mm", 2.2)),
        cutouts=cutouts,
        lens_holes=lens_holes,
        floor_cutouts=floor_cutouts,
        tripod_mount=tripod_mount,
        camera_mount=camera_mount,
        lid=lid,
        name=str(p.get("name", "enclosure")),
    )


class ParametricCadProvider:
    """Generate a watertight parametric solid as ASCII STL, no external deps."""

    provider_id = "parametric_cad"
    display_name = "Parametric code-CAD (built-in primitives)"
    adapter_version = "0.1.0"
    model_id = "builtin-parametric-box"
    capabilities = MeshGenCapabilities(
        # Natural input is a text prompt. Deliberately NOT image/gif/video, so this
        # never counts as a "live media meshgen" provider in readiness reporting —
        # it does not reconstruct a reference, it emits a parametric primitive.
        input_kinds=(InputKind.PROMPT,),
        output_formats=("stl",),
        supports_cloud=False,
        supports_local=True,
        supports_remote_delete=False,
    )

    def estimate(self, request: MeshGenRequest) -> MeshGenEstimate:
        return MeshGenEstimate(
            provider_id=self.provider_id,
            status=StageStatus.SUCCEEDED,
            cost=MeshGenCost(currency="USD", amount=0.0, estimated=False),
            estimated_seconds=0.0,
            message="Parametric code-CAD generation is local and free.",
        )

    def healthcheck(self) -> ProviderHealth:
        return ProviderHealth(
            provider_id=self.provider_id,
            status=StageStatus.SUCCEEDED,
            message="Parametric code-CAD is available (built-in box primitive, no third-party deps).",
            checked_at=utc_now(),
        )

    def generate(self, request: MeshGenRequest, run: RunLayout) -> MeshGenResult:
        started_perf = time.perf_counter()
        started_at = utc_now()

        run.meshgen_dir.mkdir(parents=True, exist_ok=True)
        primitive = str(request.provider_params.get("primitive", "box")).lower()
        if primitive == "enclosure":
            destination, geo_metadata = self._write_enclosure(request, run.meshgen_dir)
        elif primitive == "lid":
            destination, geo_metadata = self._write_lid(request, run.meshgen_dir)
        elif primitive == "grip":
            destination, geo_metadata = self._write_grip(request, run.meshgen_dir)
        elif primitive == "faceplate":
            destination, geo_metadata = self._write_faceplate(request, run.meshgen_dir)
        else:
            destination, geo_metadata = self._write_box(request, run.meshgen_dir)

        output_hash = sha256_file(destination)
        ended_at = utc_now()
        run_seconds = max(0.0, time.perf_counter() - started_perf)
        artifact = Artifact(
            kind=ArtifactKind.GENERATED_MESH,
            path=destination,
            label="Parametric code-CAD mesh",
            metadata={
                "provider_id": self.provider_id,
                "format": "ascii_stl",
                "sha256": output_hash,
                **geo_metadata,
            },
        )
        result = MeshGenResult(
            status=StageStatus.SUCCEEDED,
            provider_id=self.provider_id,
            model_id=self.model_id,
            timing=MeshGenTiming(
                started_at=started_at,
                ended_at=ended_at,
                queue_seconds=0.0,
                run_seconds=run_seconds,
                download_seconds=0.0,
                wall_seconds=run_seconds,
            ),
            cost=MeshGenCost(currency="USD", amount=0.0, estimated=False),
            attempt_count=1,
            raw_output_path=destination,
            normalized_mesh_path=destination,
            artifact=artifact,
            output_hashes={str(destination): output_hash},
        )
        write_provider_receipts(result, run)
        return result

    def delete_remote_artifacts(self, result: MeshGenResult) -> DeleteResult:
        return DeleteResult(
            status=StageStatus.SKIPPED,
            message="Parametric code-CAD creates no remote artifacts.",
        )

    def _write_box(self, request: MeshGenRequest, meshgen_dir: Path) -> tuple[Path, dict[str, Any]]:
        dimensions_mm = _resolve_box_mm(request)
        triangles = _build_box_triangles(dimensions_mm)
        destination = self._destination_path(meshgen_dir, "box")
        _write_ascii_stl(destination, "parametric_cad_box", triangles)
        return destination, {
            "primitive": "box",
            "dimensions_mm": list(dimensions_mm),
            "triangle_count": len(triangles),
        }

    def _write_enclosure(self, request: MeshGenRequest, meshgen_dir: Path) -> tuple[Path, dict[str, Any]]:
        from printpipe.meshgen.enclosure import enclosure_ascii_stl

        spec = _enclosure_spec_from_params(request.provider_params.get("enclosure") or {})
        text = enclosure_ascii_stl(spec)
        destination = self._destination_path(meshgen_dir, "enclosure")
        destination.write_text(text, encoding="ascii")
        return destination, {
            "primitive": "enclosure",
            "dimensions_mm": [spec.outer_length_mm, spec.outer_width_mm, spec.total_height_mm],
            "board_mm": [spec.board_length_mm, spec.board_width_mm],
            "triangle_count": text.count("facet normal"),
        }

    def _write_lid(self, request: MeshGenRequest, meshgen_dir: Path) -> tuple[Path, dict[str, Any]]:
        from printpipe.meshgen.enclosure import lid_ascii_stl

        spec = _enclosure_spec_from_params(request.provider_params.get("enclosure") or {})
        if spec.lid is None:
            raise ValueError("primitive 'lid' requires an 'enclosure.lid' params block")
        text = lid_ascii_stl(spec)
        destination = self._destination_path(meshgen_dir, "lid")
        destination.write_text(text, encoding="ascii")
        return destination, {
            "primitive": "lid",
            "dimensions_mm": [spec.outer_length_mm, spec.outer_width_mm, spec.lid.thickness_mm],
            "triangle_count": text.count("facet normal"),
        }

    def _write_grip(self, request: MeshGenRequest, meshgen_dir: Path) -> tuple[Path, dict[str, Any]]:
        from printpipe.meshgen.enclosure import GripSpec, grip_ascii_stl

        params = dict(request.provider_params.get("grip") or {})
        spec = GripSpec(
            mount_span_mm=float(params.get("mount_span_mm", 110.0)),
            standoff_mm=float(params.get("standoff_mm", 45.0)),
            bar_mm=float(params.get("bar_mm", 18.0)),
            leg_mm=float(params.get("leg_mm", 14.0)),
            mount_hole_dia_mm=float(params.get("mount_hole_dia_mm", 2.7)),
            name=str(params.get("name", "grip")),
        )
        text = grip_ascii_stl(spec)
        destination = self._destination_path(meshgen_dir, "grip")
        destination.write_text(text, encoding="ascii")
        return destination, {
            "primitive": "grip",
            "dimensions_mm": [spec.mount_span_mm, spec.standoff_mm, spec.bar_mm],
            "triangle_count": text.count("facet normal"),
        }

    def _write_faceplate(self, request: MeshGenRequest, meshgen_dir: Path) -> tuple[Path, dict[str, Any]]:
        from printpipe.meshgen.enclosure import FaceplateSpec, faceplate_ascii_stl

        params = dict(request.provider_params.get("faceplate") or {})
        mount_holes = tuple((float(x), float(y)) for x, y in params.pop("mount_holes_xy", []) or [])
        center = params.pop("lens_center_xy", [0.0, 0.0]) or [0.0, 0.0]
        spec = FaceplateSpec(
            length_mm=float(params.get("length_mm", 44.0)),
            width_mm=float(params.get("width_mm", 44.0)),
            thickness_mm=float(params.get("thickness_mm", 3.0)),
            lens_hole_dia_mm=float(params.get("lens_hole_dia_mm", 40.0)),
            lens_center_xy=(float(center[0]), float(center[1])),
            mount_holes_xy=mount_holes,
            mount_hole_dia_mm=float(params.get("mount_hole_dia_mm", 2.75)),
            name=str(params.get("name", "faceplate")),
        )
        text = faceplate_ascii_stl(spec)
        destination = self._destination_path(meshgen_dir, "faceplate")
        destination.write_text(text, encoding="ascii")
        return destination, {
            "primitive": "faceplate",
            "dimensions_mm": [spec.length_mm, spec.width_mm, spec.thickness_mm],
            "lens_hole_dia_mm": spec.lens_hole_dia_mm,
            "triangle_count": text.count("facet normal"),
        }

    def _destination_path(self, meshgen_dir: Path, stem: str = "box") -> Path:
        destination = meshgen_dir / f"{self.provider_id}_{stem}.stl"
        if not destination.exists():
            return destination
        index = 2
        while True:
            candidate = meshgen_dir / f"{self.provider_id}_{stem}-{index}.stl"
            if not candidate.exists():
                return candidate
            index += 1


__all__ = ["ParametricCadProvider", "DEFAULT_BOX_MM"]
