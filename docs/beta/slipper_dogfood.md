# Slipper Dogfood Validation

Status: software dogfood checklist for the slipper proof-of-concept path. The
slipper has not been physically printed by PrintPipe.

Use this page to decide whether the slipper can move from referenced proof of
concept to a PrintPipe-owned beta validation run. Do not mark the dogfood pass
until every software gate and every physical gate below has evidence.

## Proof-of-Concept Path

The honest beta path is existing slipper mesh -> PrintPipe run folder -> Bambu
bundle/slice receipts -> flex coupon first -> physical slipper print. The
current slipper artifacts live outside this repo and are indexed by
`examples/slipper_poc_manifest.json`; large meshes, 3MFs, GLBs, and G-code stay
in `/Users/zohartito/Desktop/slipper_3d`.

Use the final repaired STL from the external manifest for the first dogfood
attempt. Use the upstream V2c GLB only after PrintPipe can run the mesh repair
stage and write repair receipts itself.

## What To Run

Check local setup:

```bash
printpipe doctor
```

Check the current software evidence and fixture gates:

```bash
pytest tests/test_slipper_manifest.py \
  tests/test_bambu_slicer_slipper_fixture.py \
  tests/test_existing_stl_pipeline_bundle.py
```

Create a current CLI run folder for the repaired slipper STL when the external
slipper repo is present:

```bash
printpipe run /Users/zohartito/Desktop/slipper_3d/output/slipper_size11_v2c_repaired_textured.stl --runs-dir runs
printpipe status runs/<run-id>
printpipe open-report runs/<run-id>
```

If validating the existing-mesh pipeline directly before the CLI wires it in,
run the library path and record the printed run root:

```bash
python - <<'PY'
from pathlib import Path
from printpipe.pipeline import run_existing_mesh_pipeline

result = run_existing_mesh_pipeline(
    Path("/Users/zohartito/Desktop/slipper_3d/output/slipper_size11_v2c_repaired_textured.stl"),
    Path("runs"),
)
print(result.layout.root)
PY
```

## Artifacts To Inspect

- `examples/slipper_poc_manifest.json`: required external artifact IDs, sizes,
  and hashes.
- External repair stats for V2c and the final textured STL: topology before and
  after repair.
- `runs/<run-id>/manifest.json`: input path, run ID, and immutable run layout.
- `runs/<run-id>/20_meshgen/`: imported or generated mesh actually used by the
  PrintPipe run.
- `runs/<run-id>/60_bambu/`: Bambu-native `.3mf` bundle when generated.
- `runs/<run-id>/80_reports/run_report.json`, `.md`, and `.html`: stage status,
  warnings, artifacts, and pre-print checklist.
- Bambu slice log/result/estimate JSON: return code, warnings, time, filament
  mass, layer count, and any enum substitutions.
- Physical evidence folder or notes: coupon photos, slipper photos, measured
  dimensions, filament drying log, printer/profile versions, and operator notes.

## Gates And Pass/Fail Criteria

Mesh repair

Pass: repair receipts show the dogfood mesh is watertight with no non-manifold
edges or open boundary edges after repair, and the repaired mesh is the mesh
used for bundling. Fail: repair is skipped for an upstream generated mesh,
topology remains invalid, or the repaired artifact cannot be traced to the
bundle.

Bed fit

Pass: the oriented slipper fits the selected Bambu bed with Z on the plate and
positive XY margin. The known v3 reference was about 229.73 x 234.08 x 63.03 mm
on a 256 x 256 mm P2S bed. Fail: any bounding box extends outside the bed, the
object floats below/above the plate unexpectedly, or fit depends on an
unrecorded manual transform.

Support/cantilever

Pass: support settings are valid for Bambu Studio, supports are enabled for the
slipper overhang risk, and slicer logs show no blocker warning for floating
cantilever, unsupported islands, or enum replacement. Fail: the slice log
contains support/cantilever blockers, Bambu silently replaces a profile enum, or
the report cannot explain the support policy.

Slice estimate

Pass: Bambu CLI slicing succeeds, the estimate parser records time, filament
mass, cost if available, and layer count, and the numbers are plausible against
the known v3 estimate of roughly 21h 30m, 195.7 g, and 425 layers. Fail: the CLI
returns non-zero, errors or blocker warnings are present, estimate fields are
missing, or the estimate is clearly inconsistent with the selected mesh/profile.

Flex coupon first

Pass: a small TPU flex coupon is printed with the same printer, filament family,
drying process, and relevant profile settings before the slipper print. It
should show acceptable adhesion, flex, stringing, and layer bonding. Fail: the
coupon is skipped, the coupon fails mechanically, or settings are changed for
the slipper without re-validating the coupon.

Physical print outcome

Pass: a slipper is physically printed from a PrintPipe-generated bundle, the run
folder and slice receipt match the printed job, and the result is inspected for
adhesion, delamination, sole texture, fit, and basic wear safety. Fail: no
PrintPipe-generated slipper has been printed, the print fails, the printed
object differs from the recorded bundle, or inspection finds unsafe/ unusable
geometry. This gate is currently pending because the slipper has not been
physically printed by PrintPipe.

## Physical Steps Still Required

- Dry the TPU filament and record the dryer settings/time.
- Print the flex coupon first and save photos plus notes in the run evidence.
- Open the generated `.3mf` in Bambu Studio and inspect layer preview before
  starting the full slipper.
- Print the slipper from the PrintPipe-generated bundle, not from the older
  external v3 bundle.
- Record printer model, nozzle, Bambu Studio version, filament spool, profile
  IDs, slice estimate, print duration, mass used, photos, and measured fit.
- Update the run report or beta notes with the physical print outcome, including
  failures.
