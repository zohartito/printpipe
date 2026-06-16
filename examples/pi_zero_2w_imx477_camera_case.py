"""Product recipe: "Handycam Mk2" — camcorder body + screw-down lid + a 3D-printed hand grip,
for Raspberry Pi Zero 2 W + HQ Camera (IMX477) + CS lens.

Three printed parts:
  1. body  - horizontal camcorder shell; lens front, Pi inside, ports, bracket floor opening.
  2. lid   - flat screw-down top.
  3. grip  - a bail / suitcase-style hand grip that bolts to the RIGHT wall; the bar stands
             off ~45mm so a big hand wraps it. FULLY PRINTED handheld part (replaces the
             fabric strap). The bar bridges ~96mm between the legs, so supports are enabled.

Tripod: the camera's existing ArduCam metal bracket (brass 1/4-20) drops through the front
floor opening and mounts to the tripod (Option A) - NO printed thread.

Port positions from the official Pi Zero 2 W mechanical drawing:
  - micro-USB POWER is 12.4mm from the SD-end edge (NOT centered) -> cut at u=-31 on +y wall.
  - the microSD slot is NOT dimensioned on the drawing; it sits ~centered on its short edge.
    The cutout here is widened (22mm) to tolerate the offset - CALIPER your board to confirm.

v1 MOCKUP. Also caliper: ArduCam bracket footprint + 1/4-20 position, CS lens mount-ring OD,
micro-USB plug envelope, SanDisk protrusion, CSI ribbon service-loop volume.

Sliced for Bambu PLA Basic (practice prototypes) with per-part slicer overrides
(supports + wall loops + infill + layer height). Open STLs (not the .3mf) in Bambu Studio.
Run:  .venv/bin/python examples/pi_zero_2w_imx477_camera_case.py
"""

from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

from printpipe.contracts import InputKind
from printpipe.fabrication import Dimension, FitContext, Provenance
from printpipe.meshgen.contracts import MeshGenRequest
from printpipe.meshgen.parametric_cad import ParametricCadProvider
from printpipe.pipeline import PipelineError, run_existing_mesh_pipeline
from printpipe.runs.paths import create_prompt_run

REPO = Path(__file__).resolve().parent.parent
RUNS = REPO / "runs"

CASE = {
    "board_length_mm": 114.0,   # -> inner 116 (X, front-to-back)
    "board_width_mm": 46.0,     # -> inner 48 (Y)
    "internal_height_mm": 52.0, # clears the 38mm camera lifted for the ribbon fold
    "wall_mm": 2.4,
    "floor_mm": 3.0,
    "clearance_mm": 1.0,
    # Pi + PiSugar stack at the BACK, on its M2.5 58x23 pattern (one screw set captures both).
    "mount_holes_xy": [[4, 11.5], [4, -11.5], [-54, 11.5], [-54, -11.5]],
    "standoff_height_mm": 4.0,  # lifts the PiSugar off the floor; the stack rises above
    "standoff_outer_dia_mm": 6.0,
    "screw_hole_dia_mm": 2.2,   # M2.5 self-tap through PiSugar + Pi into the standoff
    "cutouts": [
        # All three data ports on the -y long wall (flipped), at the Pi+PiSugar board height.
        # Order from the SD end (-x, back) -> CSI end (+x, front): mini-HDMI, USB, PWR.
        {"face": "-y", "u_mm": -45.5, "z_center_mm": 16.0, "width_mm": 14.0, "height_mm": 12.0},  # mini-HDMI
        {"face": "-y", "u_mm": -16.5, "z_center_mm": 16.0, "width_mm": 11.0, "height_mm": 12.0},  # micro-USB (data)
        {"face": "-y", "u_mm": -3.5,  "z_center_mm": 16.0, "width_mm": 11.0, "height_mm": 12.0},  # micro-USB (PWR IN)
        # microSD on the SD short edge (-x, back); widened for the undimensioned offset.
        {"face": "-x", "u_mm": 0.0, "z_center_mm": 16.0, "width_mm": 22.0, "height_mm": 7.0},
    ],
    "lens_holes": [
        # Front wall (+x): the lens sits INSIDE the box, recessed; the O38 hole just lets it see
        # out (no protruding collar). Raised to v=30 so the ribbon can fold under the camera.
        {"face": "+x", "u_mm": 0.0, "v_mm": 30.0, "diameter_mm": 38.0},
        # Grip-screw clearance on the +y wall (opposite the ports): 110mm apart, at handle height.
        {"face": "+y", "u_mm": -55.0, "v_mm": 24.0, "diameter_mm": 3.4},
        {"face": "+y", "u_mm": 55.0, "v_mm": 24.0, "diameter_mm": 3.4},
    ],
    # HQ camera bolts to 4 LONG standoffs off the front wall, so the board sits ~44mm back and
    # the ~45mm lens is fully inside (tip near the front hole). Held at v=30 so the lens lines up
    # and the ribbon (board's bottom edge) has ~9mm to fold inside.  post_len ~= lens length.
    "camera_mount": {"v_center_mm": 30.0, "pitch_mm": 30.0, "post_len_mm": 44.0,
                     "post_dia_mm": 7.0, "pilot_dia_mm": 2.1},
    "floor_cutouts": [
        # Small opening under the camera ONLY for the metal bracket's 1/4-20 to reach a tripod.
        # (No ribbon hole -- the ribbon stays inside and folds in the gap under the camera.)
        {"x_mm": 22.0, "y_mm": 0.0, "size_x_mm": 20.0, "size_y_mm": 18.0},
    ],
    "lid": {
        "thickness_mm": 2.4, "boss_dia_mm": 7.0, "boss_pilot_dia_mm": 2.5,
        "screw_clearance_dia_mm": 3.4, "pilot_depth_mm": 9.0,
        "boss_xy": [[-50, 20], [-50, -20], [5, 20], [5, -20]],
    },
    "name": "pi_imx477_handycam_mk4",
}

# Printed bail/suitcase hand grip (bolts to the +y wall; round bar a hand wraps).
# bar 16 = slimmer round bar; mount holes O4.0 = M3 heat-set insert pockets.
GRIP = {
    "mount_span_mm": 110.0, "standoff_mm": 45.0, "bar_mm": 16.0, "leg_mm": 14.0,
    "mount_hole_dia_mm": 4.0, "name": "handycam_grip",
}

# Dimension provenance for the fit-critical numbers in CASE/GRIP. Datasheet/measured dims
# are grounded; the caliper-TODO numbers in this v1 mockup (the recipe header calls them out)
# are ASSUMED + fit_critical, so they hold the build out of "ready to print" until measured.
DIMENSIONS = [
    Dimension("board_length_mm", 114.0, Provenance.DATASHEET, fit_critical=True,
              source="Pi Zero 2 W mechanical drawing"),
    Dimension("board_width_mm", 46.0, Provenance.DATASHEET, fit_critical=True,
              source="Pi Zero 2 W mechanical drawing"),
    Dimension("clearance_mm", 1.0, Provenance.MEASURED, source="chosen build tolerance"),
    Dimension("standoff_height_mm", 4.0, Provenance.MEASURED, source="PiSugar standoff (design)"),
    Dimension("mount_span_mm", 110.0, Provenance.MEASURED, fit_critical=True,
              source="= body +y grip-hole span"),
    # Caliper TODOs (recipe header) - guessed, fit-critical -> block ready_to_print until measured.
    Dimension("stack_height_mm", 48.0, Provenance.ASSUMED, fit_critical=True,
              source="caliper TODO: HQ camera (~38mm) + CSI ribbon fold (~9mm)"),
    Dimension("microsd_offset_mm", 0.0, Provenance.ASSUMED, fit_critical=True,
              source="caliper TODO: microSD not dimensioned on the drawing"),
    Dimension("lens_length_mm", 45.0, Provenance.ASSUMED, fit_critical=True,
              source="caliper TODO: CS lens mount-ring"),
    Dimension("arducam_bracket_footprint_mm", 18.0, Provenance.ASSUMED, fit_critical=True,
              source="caliper TODO: ArduCam bracket + 1/4-20 position"),
]


def fit_context() -> FitContext:
    """Build the dependency-light FitContext for this recipe from CASE / GRIP / DIMENSIONS."""
    inner_length_mm = CASE["board_length_mm"] + 2 * CASE["clearance_mm"]
    inner_width_mm = CASE["board_width_mm"] + 2 * CASE["clearance_mm"]
    total_height_mm = CASE["floor_mm"] + CASE["internal_height_mm"]
    return FitContext(
        board_length_mm=CASE["board_length_mm"],
        board_width_mm=CASE["board_width_mm"],
        inner_length_mm=inner_length_mm,
        inner_width_mm=inner_width_mm,
        internal_height_mm=CASE["internal_height_mm"],
        total_height_mm=total_height_mm,
        clearance_mm=CASE["clearance_mm"],
        wall_mm=CASE["wall_mm"],
        floor_mm=CASE["floor_mm"],
        standoff_height_mm=CASE["standoff_height_mm"],
        cutouts=[dict(cutout) for cutout in CASE["cutouts"]],
        lens={"v_mm": 30.0, "length_mm": 45.0},
        camera={
            "v_center_mm": CASE["camera_mount"]["v_center_mm"],
            "post_len_mm": CASE["camera_mount"]["post_len_mm"],
        },
        floor_cutouts=[dict(cutout) for cutout in CASE["floor_cutouts"]],
        bracket_footprint_mm=(18.0, 16.0),
        mount_holes_xy=[tuple(point) for point in CASE["mount_holes_xy"]],
        grip={"mount_span_mm": GRIP["mount_span_mm"], "mount_hole_dia_mm": GRIP["mount_hole_dia_mm"]},
        body_grip_holes={"u_positions": [-55.0, 55.0], "diameter_mm": 3.4},
        dimensions=DIMENSIONS,
    )


# Per-part Bambu slicer overrides (PLA practice prototypes). Values are list-of-strings to
# match the project_settings.config keyspace. These are written straight into each part's .3mf.
SLICE_BODY = {
    "enable_support": ["1"], "support_type": ["tree(auto)"], "support_style": ["snug"],
    "wall_loops": ["4"], "sparse_infill_density": ["20%"],
    "layer_height": ["0.20"], "line_width": ["0.42"],
}
SLICE_LID = {  # flat plate prints face-down: no supports, lighter
    "enable_support": ["0"], "wall_loops": ["3"], "sparse_infill_density": ["15%"],
    "layer_height": ["0.20"],
}
SLICE_GRIP = {  # bail bar bridges ~96mm: supports required, strong walls + dense infill
    "enable_support": ["1"], "support_type": ["tree(auto)"], "support_style": ["snug"],
    "wall_loops": ["4"], "sparse_infill_density": ["40%"], "layer_height": ["0.20"],
}

PARTS = [
    ("body", "enclosure", {"primitive": "enclosure", "enclosure": CASE}, SLICE_BODY),
    ("lid", "lid", {"primitive": "lid", "enclosure": CASE}, SLICE_LID),
    ("grip", "grip", {"primitive": "grip", "grip": GRIP}, SLICE_GRIP),
]


def main() -> None:
    provider = ParametricCadProvider()
    for label, primitive, provider_params, slice_overrides in PARTS:
        run_id = f"handycam-mk4-{label}"
        gen_root = RUNS / f"gen-{run_id}"
        if gen_root.exists():
            shutil.rmtree(gen_root)
        gen = create_prompt_run(run_id, RUNS, run_id=f"gen-{run_id}")
        request = MeshGenRequest(
            input_kind=InputKind.PROMPT, source_paths=(), output_formats=("stl",),
            provider_params=provider_params, max_attempts=1,
        )
        result = provider.generate(request, gen)
        stl = Path(result.artifact.path)
        meta = result.artifact.metadata
        print(f"\n=== {label} ({primitive}) ===")
        print(f"  generated: {stl} ({stl.stat().st_size}B)  dims_mm={meta.get('dimensions_mm')}")
        try:
            run_existing_mesh_pipeline(
                stl, RUNS, material="Bambu PLA Basic", run_slice=True,
                process_overrides=slice_overrides,
            )
        except PipelineError as exc:
            print(f"  pipeline error: {exc.args[0]}")
            continue
        slug = stl.stem.replace("_", "-")
        run_dir = sorted(d for d in RUNS.glob(f"*{slug}*") if d.is_dir())[-1]
        bundles = list(run_dir.rglob("*.3mf"))
        if bundles:
            with zipfile.ZipFile(bundles[0]) as bundle:
                cfg = json.loads(bundle.read("Metadata/project_settings.config"))
            shown = {key: cfg.get(key) for key in slice_overrides}
            print(f"  slicer settings applied: {shown}")
        gcode = list(run_dir.rglob("*.gcode"))
        if gcode:
            layers = gcode[0].read_text(errors="ignore").count("; CHANGE_LAYER")
            print(f"  SLICED (PLA prototype): {gcode[0].relative_to(RUNS)}  layers={layers}")
        print(f"  STL: {stl}")


if __name__ == "__main__":
    main()
