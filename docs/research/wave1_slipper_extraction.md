# Wave 1 Slipper Extraction Audit

Agent C audit of `/Users/zohartito/Desktop/slipper_3d` for reusable PrintPipe code and fixtures. Scope prioritized `pipeline/repair_mesh.py`, `build_3mf.py`, `orient_and_scale.py`, `apply_sole_displacement.py`, `output/*.json`, `RETROSPECTIVE.md`, and `AUDIT.md`, with supporting reads of tests, slice tooling, profile sources, and project docs.

## Reusable Modules

### Mesh repair and topology validation

Source: `/Users/zohartito/Desktop/slipper_3d/pipeline/repair_mesh.py`

- `load_mesh(path)` is a clean `trimesh.load(..., force="mesh", process=False)` wrapper that rejects non-single-mesh loads.
- `topological_counts(mesh)` is directly reusable. It reports vertices, faces, watertightness, Euler number, boundary edges, and non-manifold edges by counting sorted face edges. This should become PrintPipe's first topology gate.
- `repair_mesh(mesh, fill_holes=True)` is the best immediate port. The sequence is simple and proven: merge vertices, remove duplicate faces, remove degenerate faces, remove unreferenced vertices, optionally fill holes, then fix normals.
- `stats_for_repair(before, after)` already emits the right receipt shape for run artifacts.
- Keep the CLI behavior, but make paths run-folder relative and make "allow non-watertight" an explicit failed-or-warning policy.

Evidence from slipper artifacts:

- `output/slipper_shape_v2c_repair_stats.json`: V2c source went from 124,760 faces, not watertight, Euler 3359, 1 non-manifold edge to 121,400 faces, watertight, Euler 0, 0 non-manifold edges.
- `output/slipper_size11_v2c_repaired_textured_repair_stats.json`: post-displacement STL went from 364,200 duplicate vertices and 364,200 boundary edges to 60,700 vertices, 121,400 faces, watertight, 0 boundary edges.

### Bambu profile resolution and 3MF bundling

Source: `/Users/zohartito/Desktop/slipper_3d/build_3mf.py`

This is the highest-value port after mesh repair, but should be split into smaller modules:

- Profile lookup: `find_profile_json`, `load_profile`, and `resolve_inheritance` should become `printpipe.bambu.profiles`. The existing algorithm walks Bambu `inherits` chains, detects cycles, deep-flattens parent to child, and strips non-project keys like `inherits`, `instantiation`, `from`, and `type`.
- 3MF model XML: `build_3dmodel_xml` hand-emits 3MF Core XML with vertices, triangles, `p:UUID`, bed-center build item transform, and Bambu-native metadata. Keep the behavior, but replace raw string interpolation with safe XML escaping for object names.
- Metadata configs: `build_project_settings_config`, `build_model_settings_config`, and `build_slice_info_config` are reusable Bambu package primitives. They encode the important Bambu-specific contract that the mesh, printer, filament, and process profile all arrive as one native project.
- OPC package writing: the zip structure is reusable as-is: `[Content_Types].xml`, `_rels/.rels`, `3D/3dmodel.model`, `Metadata/project_settings.config`, `Metadata/model_settings.config`, `Metadata/slice_info.config`, and placeholder plate thumbnails.
- Native signature: keep the `--bambu-native` path as mandatory for PrintPipe outputs. The decisive Bambu gate is `<metadata name="Application">BambuStudio-...</metadata>` plus a `project_settings.config` header with `"name": "project_settings"`, `"from": "project"`, and a version string.

### Orientation, scale, and bed fit

Source: `/Users/zohartito/Desktop/slipper_3d/orient_and_scale.py`

- `pca_align(mesh)` is a good generic starting point for primary-axis estimation.
- `drop_to_bed(mesh)` should be ported almost unchanged. Every PrintPipe candidate orientation needs a final "min Z = 0 and XY centered" operation before fit scoring.
- `rotate_45_z(mesh)` is useful as one candidate rotation, but not as a universal rule.
- The bed-fit plot logic should move into a report/diagnostic helper that accepts bed dimensions, mesh vertices, candidate transform, and output path.
- `sole_down(mesh)` is partly reusable as a "flat-face/base detection" heuristic, but it should not assume footwear. Rename it around "largest XY-projected area side" or "likely flat base".

### Optional surface displacement

Source: `/Users/zohartito/Desktop/slipper_3d/apply_sole_displacement.py`

- Reusable later as an optional "apply grayscale displacement map to likely base" transform.
- The useful generic ideas are PCA-based UV coordinates on the XY footprint, bilinear grayscale sampling, feathered Z falloff, and re-dropping the mesh to Z=0.
- Do not put this in the Wave 2 core spine. It is slipper styling, not required for a generic slice-verified `.3mf`.

### Slice gate and stats parsing

Sources: `/Users/zohartito/Desktop/slipper_3d/slice_estimate.sh`, `/Users/zohartito/Desktop/slipper_3d/parse_gcode_stats.py`, `output/v3_cli_slice/*.json`

- `parse_gcode_stats.py` should be ported as a library, not a script. Useful pieces: Bambu time-string parsing, header/tail stat extraction, per-layer M73 remaining-time parsing, feature-role extrusion totals, JSON receipt output, and optional histogram generation.
- `slice_estimate.sh` captures the working Bambu CLI invocation: slice the `.3mf` directly and treat embedded `project_settings.config` as source of truth. Do not pass separate `--load-settings`.
- Replace the script's GUI-quitting behavior with a safer runner. The retrospective calls out foreground-app shutdown as a real process mistake.
- `output/v3_cli_slice/result.json` is a good expected-result fixture: `return_code: 0`, `warning_message: ""`, 121,400 triangles, 425 layers, 195.73 g, object bbox 229.73 x 234.08 x 63.03 at `z=0`.

### Calibration coupon generator

Source: `/Users/zohartito/Desktop/slipper_3d/generate_flex_coupon.py`

- Tiny but useful: generate simple material validation geometry before a long print.
- Generalize from `50 x 20 x 6` TPU coupon into a material/profile smoke-test fixture generator.

## Slipper-Specific Assumptions To Remove

- Absolute paths: `/Users/zohartito/Desktop/slipper_3d`, `/Applications/BambuStudio.app`, and fixed `output/` filenames are everywhere. PrintPipe should pass a run context/artifact registry into each stage.
- Object naming: `slipper_size11_bambu`, `slipper_size11_v2c_repaired_textured`, and profile names should become parameters.
- Printer constants: `Bambu Lab P2S 0.4 nozzle`, `C12`, 256 x 256 x 256 bed assumptions, and Bambu Studio version strings should come from printer/profile detection.
- Filament constants: SUNLU TPU 90A, black color, $20/kg, 225 C nozzle, 45 C bed, MVS 2.5, PA K=0.040, and TPU support rules belong in material rules, not generic bundling.
- Footwear sizing: `FOOT_MM = 280`, `CLEARANCE_MM = 15`, "US men's 10/11", target outer length, and 45 degree diagonal fit are slipper policy.
- Sole concepts: `sole_down`, bottom 25 percent vertex mask, heel-toe UV axes, wavy sole texture, and 0.6 mm displacement are footwear-specific unless generalized behind "base surface" APIs.
- Support conclusions: `normal(auto)`, `snug`, 0 interface top layers, 60 degree threshold, and TPU peelability are material/object heuristics. The generic system should detect support risk and validate by slice.
- Bundle placement: the working `128,128,0` transform is correct for P2S bed-center packaging but should be derived from printer bed geometry and tested against GUI/CLI behavior.
- Bambu user install behavior: cloud account path detection is useful, but profile installation is not the same as embedding profiles in a run `.3mf`; keep these paths separate.

## Files To Port First

1. `/Users/zohartito/Desktop/slipper_3d/pipeline/repair_mesh.py`

Port first into `src/printpipe/mesh/repair.py` and `src/printpipe/mesh/validate.py`. This directly satisfies the architecture hard gate that mesh topology must be validated after generation and repair.

2. `/Users/zohartito/Desktop/slipper_3d/build_3mf.py`

Split into:

- `src/printpipe/bambu/profiles.py` for profile source lookup and inheritance flattening.
- `src/printpipe/bambu/three_mf.py` for 3MF XML/config generation and OPC zip writing.
- `src/printpipe/bambu/signature.py` or constants for Bambu-native metadata requirements.

3. `/Users/zohartito/Desktop/slipper_3d/orient_and_scale.py`

Port a subset into `src/printpipe/geometry/orient.py` and `src/printpipe/geometry/bed_fit.py`: PCA axes, base detection, candidate transforms, drop-to-bed, and bed-fit visualization. Leave the slipper size defaults behind.

4. `/Users/zohartito/Desktop/slipper_3d/parse_gcode_stats.py`

Port into `src/printpipe/bambu/gcode_stats.py`. This enables the Wave 3 slice gate without depending on the shell script.

5. `/Users/zohartito/Desktop/slipper_3d/slice_estimate.sh`

Use as a reference for `src/printpipe/bambu/slicer.py`, not as production code. The production runner should detect Bambu Studio, run the CLI on a generated `.3mf`, capture logs/result JSON, and avoid force-quitting GUI apps.

6. `/Users/zohartito/Desktop/slipper_3d/apply_sole_displacement.py`

Defer until the core pipeline is green. Port only as an example transform or optional texture module.

## Tests And Fixtures To Carry Over

- `/Users/zohartito/Desktop/slipper_3d/tests/test_pipeline.py` is the best starting test map. Keep the four behaviors: repair produces watertight mesh, final mesh is on bed and within printer extents, bundle transform is bed-centered, and profile JSONs contain the v3 printability settings.
- Mesh fixture: `output/slipper_shape_v2c_multiview.glb` for repair regression. It is the realistic failing AI mesh.
- Mesh fixture: `output/slipper_size11_v2c_repaired_textured.stl` for final topology/bed-fit regression.
- JSON fixtures: `output/slipper_shape_v2c_repair_stats.json` and `output/slipper_size11_v2c_repaired_textured_repair_stats.json` for expected topology receipts.
- Profile fixtures: `profile_sources/**`, `output/SUNLU TPU 90A Slipper @BBL P2S.json`, and `output/0.20mm Slipper TPU 90A @BBL P2S.json`. Use these for inheritance flattening and settings-delta tests.
- 3MF tests: keep the synthetic box test from `test_bambu_bundle_uses_plate_center_transforms` so unit tests do not require the large slipper mesh.
- 3MF reference: `3mf_signature_findings.md` should be preserved as documentation or a test note for why Bambu-native metadata exists.
- Slice fixtures: use `output/v3_cli_slice/result.json` and `output/v3_cli_slice/slice_estimate.json` as small parser fixtures. Avoid committing the 46 MB full gcode unless a trimmed header/body/tail fixture can cover the parser.
- Coupon fixture: `generate_flex_coupon.py` can be converted into a deterministic test mesh generator for material smoke tests.

## Known Pitfalls From The Slipper Project

- AI-generated meshes are not production meshes. Hunyuan3D produced duplicate vertices, duplicate faces, degenerate triangles, and non-watertight outputs. Repair must be an explicit pipeline stage, not a late rescue.
- Repair may be needed more than once. The post-displacement STL became topologically messy again and needed a second repair pass.
- A valid 3MF zip is not enough for Bambu Studio. Without the `BambuStudio-` Application metadata and native project settings header, Bambu loads geometry only and silently drops profiles.
- Bambu GUI and CLI placement conventions can diverge. The project fixed this by keeping the STL origin-centered and using bed-center transforms in the bundle. PrintPipe should verify both package structure and slice result.
- Enum values must be source/schema checked. `support_style: "organic"` looked plausible but Bambu replaced it with `default`; valid observed values were `default` and `snug`.
- Slice early. The no-support assumption looked reasonable until CLI slicing reported a floating cantilever.
- Settings diffs need normalization. Bambu profiles mix arrays, scalars, inherited defaults, and numeric strings. A raw JSON diff overstates or misclassifies changes.
- GUI screenshots can make settings look unchanged even when JSON applied. The final product needs a settings delta receipt with reasons, not just embedded profiles.
- TPU-specific details matter. Zero brim gap can fuse to TPU, bottom shells were initially too thin, pressure advance was initially disabled for the wrong reason, and seam placement affected the toe flex zone.
- Gated web references are fragile. MakerWorld downloads hit Cloudflare 403 without a paired browser session; do not make reference `.3mf` downloads a required build step.
- Free hosted mesh generation is unreliable. HF Spaces failed in several modes before single-image Hunyuan3D worked. Provider failures should be logged and retried or routed to a local/import fallback.
- Avoid managing the user's foreground apps from automation. The slicer script's quit/kill pattern is useful history but should not be PrintPipe's default behavior.
- XML/string generation needs escaping. The POC object names were safe, but generic user filenames can contain characters that break raw XML attributes.

## Recommended Wave 2 Extraction Order

1. Establish run artifact paths and fixture loading first.

Create enough run-folder plumbing for every ported function to accept explicit input/output paths and emit JSON receipts. This removes the POC's absolute-path coupling before it spreads.

2. Port mesh validation and repair.

Bring over topology counts, repair sequencing, stats receipts, and the repair tests. This is the narrowest proven module and unblocks every downstream mesh artifact.

3. Port Bambu profile inheritance.

Load `profile_sources/**` as fixtures, resolve inheritance chains, detect cycles, flatten parent-to-child, and test expected key counts/overrides from the slipper profiles.

4. Port Bambu-native 3MF generation with a synthetic mesh.

Use a generated box first. Assert the zip member list, 3MF model metadata, `project_settings.config` header, profile identifiers, and bed-center transforms. Keep full slipper mesh packaging as an integration test later.

5. Port geometry orientation and bed-fit scoring.

Extract PCA alignment, likely-base detection, candidate rotations, drop-to-bed, and bed bounds checks. Return structured metrics before generating plots.

6. Port slice parsing and CLI runner.

Start with fixture-only parser tests from `result.json` and a trimmed gcode sample. Then add the Bambu CLI runner behind an environment/availability check so CI can skip it cleanly.

7. Integrate a minimal end-to-end slipper regression.

Use the V2c fixture to repair, orient, bundle, and validate package contents. Treat live Bambu CLI slicing as a local integration gate, not a mandatory unit test.

8. Defer sole displacement and monitor tooling.

Surface displacement, Telegram/MQTT monitoring, MakerWorld reference comparison, and install-profile UX are useful, but they are not Wave 2 core pipeline skeleton work.
