# Wave 4 Slipper Migration Comparison

Status: comparison and external artifact manifest complete.

Scope: compare PrintPipe after Wave 3 against the proven slipper v3 pipeline in
`/Users/zohartito/Desktop/slipper_3d`, then identify the safest extraction
order for turning the slipper proof of concept into a PrintPipe regression
without copying large mesh, 3MF, GLB, or G-code files into this repo.

## External Artifact Manifest

Wave 4 adds `examples/slipper_poc_manifest.json` as the local index for slipper
proof-of-concept artifacts. It references absolute paths in
`/Users/zohartito/Desktop/slipper_3d`, including:

- recommended source mesh: `output/slipper_shape_v2c_multiview.glb`
- final printable mesh: `output/slipper_size11_v2c_repaired_textured.stl`
- repair receipts for the V2c source and final textured STL
- v3 GUI and CLI Bambu-native `.3mf` bundles
- v3 slice result and parsed slice estimate
- TPU filament/process profiles and flex coupon project
- evidence docs for V2 mesh selection and real-world Bambu results

The manifest records size and SHA-256 for each entry. Large artifacts stay in
the slipper repo and are intentionally not copied into PrintPipe.

## Slipper V3 Requirements

The current slipper v3 proof needs these capabilities to be a real PrintPipe
run, not just a referenced external result:

| Requirement | Proven slipper v3 behavior | Evidence artifact |
|---|---|---|
| Select the right generated mesh | Multi-view V2c preserved the wavy sole; higher-octree single-image variants smoothed detail. | `V2_COMPARISON.md`, `slipper_shape_v2c_multiview.glb` |
| Repair generated topology | V2c source repaired from non-watertight with 1 non-manifold edge to watertight, 0 non-manifold edges. | `slipper_shape_v2c_repair_stats.json` |
| Preserve slipper-specific sole texture | Displacement and a second repair pass produced the printable textured mesh. | `slipper_size11_v2c_repaired_textured.stl`, final repair stats |
| Orient, scale, and fit P2S bed | Final object slices with bbox 229.73 x 234.08 x 63.03 mm at Z=0 on a 256 x 256 mm bed. | `v3_cli_slice/result.json` |
| Bundle as Bambu-native project | GUI and CLI `.3mf` files embed mesh, Bambu signature metadata, printer, filament, process profiles, and bed-center transform. | `Slipper_TPU90A_P2S_v3.3mf`, `Slipper_TPU90A_P2S_v3_cli.3mf` |
| Validate profile enum/settings behavior | V3 replaced rejected `support_style: organic` with `snug`, enabled supports, fixed brim gap, shells, seam, and pressure advance. | process and filament JSONs, real-world results |
| Slice-gate the actual bundle | Bambu CLI returned success, empty user-facing warning message, 121400 triangles, 425 layers, 195.73 g, 21h 30m 16s. | `v3_cli_slice/result.json`, `slice_estimate.json`, `SLICE_ESTIMATE.md` |
| Keep physical gates explicit | Software is print-viable; final layer preview, TPU coupon, filament drying, and real print remain pending. | `real_world_results.md`, `Flex_Coupon_TPU90A_P2S.3mf` |

## Current PrintPipe Capabilities

PrintPipe now has the dependency-light verification spine, but not the full
slipper implementation.

| Area | What now works in PrintPipe | Gap against slipper v3 |
|---|---|---|
| Run folders and receipts | Immutable run layout, manifest, stage directories, JSON/Markdown/HTML reports, `printpipe run/status/open-report`. | `printpipe run` stops after input preparation and reports; it does not yet orchestrate meshgen, repair, orientation, bundling, and slicing end to end. |
| Inputs | Still image, GIF, video, and existing mesh routing with honest skipped receipts for heavy processing. | No real frame extraction, background removal, lighting normalization, contact sheet, or Hunyuan3D multi-view call. |
| Mesh generation | Provider interface, existing-mesh provider, placeholders, retry/cost/time contracts. | No Hunyuan3D provider and no automated selection between V2 candidates. |
| Mesh topology | Pure-Python topology counting, validation result, JSON stats, hard failure gate. | No real mesh loader/exporter in the pipeline and no `trimesh` repair sequence from the slipper project. |
| Geometry | Bounds, Z rotations, XY centering, Z drop, bed-fit scoring, flat-base diagnostic. | No PCA alignment, semantic sole/base choice, support-burden scoring, target size inference, or bed-fit visualization. |
| Bambu profiles | Profile loading/inheritance, settings delta normalization/reporting, enum validation. | Real Bambu source discovery and slipper profile parity are not wired into an end-to-end bundle flow. |
| 3MF bundling | Minimal Bambu-native writer, required member validation, Bambu Application metadata, project/model/slice config files, GUI-safe transform primitives. | It currently packages provided `MeshGeometry`; there is no STL/GLB mesh adapter and no proven parity with the slipper v3 bundle contents. |
| Slice gate | Slicer output classifier, estimate parser for lightweight text patterns, subprocess wrapper, hard gate. | No live Bambu Studio CLI integration test has run from PrintPipe, and the rich slipper `parse_gcode_stats.py` parser is not ported. |
| Reports | JSON/Markdown/HTML skeleton reports with warnings and stage receipts. | Reports do not yet display repaired mesh, bed-fit visualization, slice logs, settings deltas, or final pre-print checklist at slipper quality. |
| Test objects | Small topology and slicer-log fixtures. | Slipper proof of concept remains external; this wave only adds the manifest and manifest validator. |

## What Now Works For Slipper Migration

- PrintPipe can safely reference the external slipper v3 artifact set through
  `examples/slipper_poc_manifest.json`.
- The manifest test validates JSON shape, absolute external paths, unique IDs,
  size/hash metadata, and required artifact existence when the slipper repo is
  present on Zohar's machine.
- The current codebase has enough contracts to start an existing-mesh slipper
  regression without inventing a new pipeline shape.
- Topology, bed-fit, profile delta, Bambu 3MF structure, slicer warnings, and
  report receipts already have unit-testable surfaces.

## What Still Needs Real Integration

- Load real STL/GLB geometry into PrintPipe data structures without making unit
  tests depend on large committed meshes.
- Port or wrap `pipeline/repair_mesh.py` so PrintPipe can repair the V2c source
  and final displaced mesh rather than only validate topology fixtures.
- Add a mesh adapter from repaired geometry into the Bambu 3MF writer.
- Reproduce the v3 Bambu-native package from PrintPipe and compare archive
  structure, metadata, profile IDs, transform policy, and settings against the
  external v3 `.3mf`.
- Port the richer G-code stats parser from `parse_gcode_stats.py` so PrintPipe
  can parse the real slipper estimate JSON shape, not just lightweight log text.
- Add a local-only Bambu CLI integration gate that skips cleanly when Bambu
  Studio is unavailable.
- Decide how slipper-specific sole displacement belongs in PrintPipe: as an
  example transform, an optional base-surface texture feature, or outside v1.
- Add physical-result receipts once the coupon and slipper are actually printed.

## Recommended Next Extraction Order

1. Add an external-artifact fixture loader around
   `examples/slipper_poc_manifest.json`.

   Keep unit tests small and skip gracefully when `/Users/zohartito/Desktop/slipper_3d`
   is absent. Use the manifest to locate realistic integration inputs locally.

2. Port real mesh load/repair/receipt behavior.

   Extract `load_mesh`, topology counts, repair sequencing, and repair stats from
   `pipeline/repair_mesh.py` into PrintPipe. First target: reproduce the two
   repair receipts already listed in the manifest.

3. Add STL/GLB to 3MF mesh adapter.

   Feed repaired geometry into the existing `MeshGeometry`/3MF writer contract.
   Compare member list, Bambu metadata, model name, transforms, and profile IDs
   against `Slipper_TPU90A_P2S_v3.3mf`.

4. Port real Bambu profile parity.

   Use the slipper filament/process JSONs and machine/profile source fixtures to
   verify inheritance flattening, enum validation, and settings delta reasons.
   Preserve the v3 fixes: snug support, support-on, 0.12 mm brim gap, 10 bottom
   shells, back seam, 225 C first layer, and pressure advance.

5. Integrate orientation, scale, and bed-fit for existing meshes.

   Start with the known final STL and expected bbox. Then move upstream to the
   V2c source mesh. Add PCA/base detection only after the existing-mesh path is
   reproducible.

6. Port rich slice-estimate parsing.

   Use `v3_cli_slice/result.json`, `slice_estimate.json`, and a trimmed G-code
   sample if needed. Keep the full 33 MB G-code external and optional.

7. Add local Bambu CLI integration.

   Slice the generated PrintPipe `.3mf` only when Bambu Studio is installed.
   Compare return code, warning message, triangle count, bbox, time, mass, layer
   count, and cost against the v3 receipts.

8. Defer Hunyuan3D and sole displacement until the existing-mesh spine passes.

   The fastest high-confidence migration path is external V2c mesh -> repair ->
   orient/fit -> bundle -> slice -> report. Hunyuan3D provider work and
   slipper-style sole displacement can follow as separate, well-bounded stages.

## Wave 4 Bottom Line

PrintPipe is ready to *reference* the slipper proof of concept and start
local-only regression work, but it cannot yet *reproduce* the v3 slipper bundle.
The next meaningful milestone is an existing-mesh slipper run that consumes the
manifest, repairs the V2c mesh, emits a Bambu-native `.3mf`, and matches the
known v3 slice receipts closely enough to become the first real test object.
