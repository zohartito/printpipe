"""Product recipe: Raspberry Pi Zero 2 W + HQ Camera (IMX477) enclosure.

Generates two parametric parts via PrintPipe's parametric-CAD provider and runs
each through the real repair -> orient -> bundle -> slice spine:

  1. Pi Zero 2 W tray (body): cavity + 4 M2.5 standoffs + micro-USB charging cutout.
  2. HQ camera faceplate (face): 4x M2.5 mounting holes (30x30 pitch) + lens hole.

Dimensions are from official Raspberry Pi mechanical drawings + a tested maker CAD
model. CALIPER-VERIFY before a final print: HQ-cam hole pitch (30mm), the micro-USB
*plug* envelope (size the cutout to the plug, not the receptacle), and the lens barrel
of YOUR specific lens (6mm CS = O30, 16mm C = O39 -> O40 hole clears either).

Run:  .venv/bin/python examples/pi_zero_2w_imx477_enclosure.py
"""

from __future__ import annotations

import shutil
from pathlib import Path

from printpipe.contracts import InputKind
from printpipe.meshgen.contracts import MeshGenRequest
from printpipe.meshgen.parametric_cad import ParametricCadProvider
from printpipe.pipeline import PipelineError, run_existing_mesh_pipeline
from printpipe.runs.paths import create_prompt_run

REPO = Path(__file__).resolve().parent.parent
RUNS = REPO / "runs"

# --- Pi Zero 2 W tray (body) -------------------------------------------------
# Board 65 x 30 mm; mount holes O2.75 at 58 x 23 pitch -> (+/-29, +/-11.5).
# micro-USB PWR centreline 12.4 mm from the left edge -> x = -32.5 + 12.4 = -20.1.
TRAY = {
    "board_length_mm": 65.0,
    "board_width_mm": 30.0,
    "internal_height_mm": 16.0,
    "wall_mm": 2.0,
    "floor_mm": 1.6,
    "clearance_mm": 0.6,
    "mount_holes_xy": [[29, 11.5], [29, -11.5], [-29, 11.5], [-29, -11.5]],
    "standoff_height_mm": 6.0,
    "standoff_outer_dia_mm": 6.0,
    "screw_hole_dia_mm": 2.2,
    "cutouts": [
        # micro-USB PWR (charging) on the bottom long edge, 12.4mm from the left edge.
        {"face": "-y", "u_mm": -20.1, "z_center_mm": 7.6, "width_mm": 12.0, "height_mm": 8.0},
        # microSD access on the short edge (SanDisk 32GB stays inserted; the push-pull card
        # protrudes a few mm, so the slot lets it clear the wall and be pulled out without
        # opening the case). This is the WITH-SD variant; delete this cutout for without-SD.
        {"face": "-x", "u_mm": 0.0, "z_center_mm": 7.0, "width_mm": 14.0, "height_mm": 5.0},
    ],
    "name": "pi_zero_2w_tray",
}

# --- HQ camera faceplate (face) ----------------------------------------------
# Camera board 38 x 38; M2.5 mount at 30 x 30 pitch -> (+/-15, +/-15).
# Lens hole O40 clears the 16mm C lens / back-focus ring (O36).
FACEPLATE = {
    "length_mm": 46.0,
    "width_mm": 46.0,
    "thickness_mm": 3.0,
    "lens_hole_dia_mm": 40.0,
    "lens_center_xy": [0.0, 0.0],
    "mount_holes_xy": [[15, 15], [15, -15], [-15, 15], [-15, -15]],
    "mount_hole_dia_mm": 2.75,
    "name": "hq_camera_faceplate",
}

PARTS = [
    ("pi-zero-2w-tray", "enclosure", "enclosure", TRAY),
    ("hq-camera-faceplate", "faceplate", "faceplate", FACEPLATE),
]


def main() -> None:
    provider = ParametricCadProvider()
    for run_id, primitive, param_key, params in PARTS:
        gen_root = RUNS / f"gen-{run_id}"
        if gen_root.exists():
            shutil.rmtree(gen_root)  # scratch dir for the generated STL; safe to recreate
        gen = create_prompt_run(run_id, RUNS, run_id=f"gen-{run_id}")
        request = MeshGenRequest(
            input_kind=InputKind.PROMPT,
            source_paths=(),
            output_formats=("stl",),
            provider_params={"primitive": primitive, param_key: params},
            max_attempts=1,
        )
        result = provider.generate(request, gen)
        stl = Path(result.artifact.path)
        meta = result.artifact.metadata
        print(f"\n=== {run_id} ===")
        print(f"  generated: {stl.name} ({stl.stat().st_size}B)  outer={meta.get('dimensions_mm')}")
        try:
            run_existing_mesh_pipeline(stl, RUNS, material="Bambu PC", run_slice=True)
            ok = True
        except PipelineError as exc:
            ok = False
            print(f"  pipeline error: {exc.args[0]}")
        if ok:
            slug = stl.stem.replace("_", "-")
            matches = sorted(d for d in RUNS.glob(f"*{slug}*") if d.is_dir())
            run_dir = matches[-1]
            gcode = list(run_dir.rglob("*.gcode"))
            bundle = list(run_dir.rglob("*.3mf"))
            if gcode:
                layers = gcode[0].read_text(errors="ignore").count("; CHANGE_LAYER")
                print(f"  SLICED: {gcode[0].relative_to(RUNS)}  layers={layers}")
            if bundle:
                print(f"  bundle: {bundle[0].relative_to(RUNS)}")


if __name__ == "__main__":
    main()
