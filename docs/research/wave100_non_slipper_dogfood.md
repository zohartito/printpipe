# Wave 100 Non-Slipper Dogfood

Status: complete for software/slicer dogfood. This is not physical print proof.

## Goal

Run three non-slipper objects through the real local PrintPipe path with live
Bambu CLI slicing enabled, then turn every discovered software failure into a
code fix and regression test before counting the run as evidence.

## Objects

| Object | Fixture | Material intent |
| --- | --- | --- |
| Figurine | `tests/fixtures/objects/figurine/simple_figurine_ascii.stl` | Bambu PLA Basic |
| Cup/vase | `tests/fixtures/objects/cup_vase/cup_vase_open_frustum.stl` | Bambu PLA Basic |
| Flat bracket | `tests/fixtures/objects/flat_bracket/flat_bracket.stl` | Bambu PETG Basic |

## Failures Found

1. `trimesh.repair.fill_holes()` imported `networkx` lazily during real repair.
   `pyproject.toml` and environment diagnostics only treated `trimesh` as the
   optional mesh-repair dependency, so cup/vase dogfood first crashed with
   `ModuleNotFoundError: No module named 'networkx'`.
2. The cup/vase fixture is intentionally open at the rim. The pipeline already
   called mesh repair with `allow_non_watertight=True`, but the repair function
   still returned a failed stage when boundary edges remained.
3. The flat bracket is 300 mm long. Bed-fit preview selected a 45 degree Z
   rotation that fits a 256 mm bed, but the oriented STL and `.3mf` were still
   written at 0 degrees. Bambu CLI rejected the bundle as an empty/off-bed plate.

## Fixes

- Added `networkx>=3.0` to the `mesh-repair` extra.
- Added `networkx` to preflight/doctor dependency checks.
- Mesh repair now records the actual missing dependency when an optional repair
  backend import fails during repair.
- `allow_non_watertight=True` now returns a successful repair receipt with the
  remaining boundary/non-manifold counts in the message.
- Existing-mesh pipeline now applies the selected bed-fit orientation before
  writing the oriented ASCII STL, model preview, bed-fit preview, and Bambu
  bundle.

## Commands Run

```bash
.venv/bin/printpipe run tests/fixtures/objects/figurine/simple_figurine_ascii.stl --runs-dir runs/dogfood --material "Bambu PLA Basic" --printer "Bambu Lab P2S" --use-case "dogfood fixture" --slice
.venv/bin/printpipe run tests/fixtures/objects/cup_vase/cup_vase_open_frustum.stl --runs-dir runs/dogfood --material "Bambu PLA Basic" --printer "Bambu Lab P2S" --use-case "dogfood fixture" --slice
.venv/bin/printpipe run tests/fixtures/objects/flat_bracket/flat_bracket.stl --runs-dir runs/dogfood --material "Bambu PETG Basic" --printer "Bambu Lab P2S" --use-case "dogfood fixture" --slice
```

`runs/dogfood/` is intentionally ignored by git. The run IDs below are local
evidence pointers, not committed artifacts.

## Successful Evidence

| Object | Run ID | Repair | Orientation / bed fit | Slice receipt |
| --- | --- | --- | --- | --- |
| Figurine | `20260528-144457-simple-figurine-ascii` | watertight, 0 boundary edges | 0 deg, 16.0 x 10.0 x 34.0 mm, 240.0 mm margin | succeeded, 831s, 1.68g, 170 layers, 0 warnings |
| Cup/vase | `20260528-144446-cup-vase-open-frustum` | intentionally open rim, 6 boundary edges allowed | 45 deg, 31.1 x 31.1 x 30.0 mm, 224.9 mm margin | succeeded, 1338s, 6.07g, 150 layers, 0 warnings |
| Flat bracket | `20260528-144421-flat-bracket` | watertight, 0 boundary edges | 45 deg, 222.7 x 222.7 x 4.0 mm, 33.3 mm margin | succeeded, 3408s, 28.18g, 20 layers, 0 warnings |

## Verification

```bash
.venv/bin/pytest tests/test_mesh_repair.py tests/test_env_dependencies.py tests/test_env_doctor.py tests/test_pipeline_existing_mesh.py tests/test_beta_onboarding_docs.py tests/test_beta_non_slipper_runs_doc.py
.venv/bin/python -m compileall -q src
git diff --check
.venv/bin/pytest
```

## Boundary

This wave proves the software dogfood path for three non-slipper fixture
classes through Bambu-native `.3mf` generation and live Bambu CLI slicing on
this Mac. It does not prove physical print success, material behavior, support
quality, durability, or trusted-user usability.
