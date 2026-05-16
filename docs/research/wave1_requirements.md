# PrintPipe V1 Requirements and Acceptance Criteria

Status: Wave 1 requirements draft

## Product Goal

PrintPipe v1 is a local-first Mac/Windows pipeline that turns an image, GIF,
video, or existing mesh plus Bambu printer, filament, and size intent into a
Bambu-ready print package.

The product is not mesh generation by itself. The product is the verified bridge
from messy reference input to a repaired, oriented, bed-fit, profile-tuned,
slice-verified Bambu `.3mf` with receipts that explain what happened.

The first shippable milestone is a reproducible run folder from a command like:

```bash
printpipe run input.gif \
  --printer "Bambu Lab P2S 0.4 nozzle" \
  --filament "SUNLU TPU 90A" \
  --target-size 295mm
```

## Non-Goals

- Public web app, hosted accounts, auth, billing, queues, object storage, or
  cloud-only operation.
- Non-Bambu printer support.
- Multi-material, AMS, color painting, or multi-plate project authoring.
- Starting a physical print job automatically.
- Guaranteeing that an AI mesh provider can reconstruct every reference image.
- Requiring Rhino, Blender UI, Bambu Studio UI edits, or manual mesh repair for
  the happy path.
- Hiding failures behind a partial download. A run that cannot pass gates must
  fail with a receipt, not produce a pretend-success bundle.

## What One-Shot Means

One-shot means a user supplies the input and print intent once, then PrintPipe
either produces a slice-verified Bambu `.3mf` or a clear failed-run receipt.

For a successful one-shot run:

- The user does not manually repair geometry.
- The user does not manually move, rotate, or scale the model onto the bed.
- The user does not manually select or fix printer, filament, or process
  profiles in Bambu Studio.
- The app may retry providers, repairs, orientations, scale decisions, or process
  settings internally.
- The app may ask for required missing intent, such as target size, before the
  run starts.
- The app only calls the result successful after Bambu CLI slicing passes.

One-shot does not mean every input succeeds. It means the pipeline owns all
recoverable work and reports unrecoverable failures precisely.

## V1 User Flow

1. User starts a local run through the CLI. A local UI can call the same pipeline
   later, but the CLI is the first acceptance surface.
2. PrintPipe creates one immutable run folder and stores the original input,
   command options, environment summary, and selected printer/filament intent.
3. Input processing accepts:
   - still image
   - GIF
   - video
   - existing mesh
4. For GIF/video inputs, PrintPipe extracts frames, selects useful reference
   frames, removes background where needed, normalizes lighting/contrast, and
   writes a contact sheet.
5. Mesh generation runs through a provider interface. Providers can be hosted
   GPU, local model, API provider, or existing-mesh import. Provider retries,
   fallback attempts, time, cost, and errors are logged.
6. PrintPipe scans generated/imported mesh topology, repairs it locally, then
   validates the repaired mesh. A mesh that remains non-watertight or invalid
   fails the run.
7. PrintPipe estimates bounding box, likely axes, flat bases/openings when
   possible, and candidate orientations. It keeps up to three candidates
   internally and advances the first one that passes bed-fit and slice gates.
8. PrintPipe applies target size, checks Bambu bed dimensions, rotates or scales
   only according to explicit rules, drops the object to the bed, and writes a
   bed-fit preview.
9. PrintPipe loads Bambu printer, filament, and process profile defaults, applies
   material-aware overrides, validates enum values against the Bambu-compatible
   schema/source, and records a reason for every changed setting.
10. PrintPipe builds a Bambu-native `.3mf` containing the model, printer profile,
    filament profile, process profile, metadata signature, and GUI-safe bed
    transform.
11. PrintPipe validates the `.3mf` contents, runs Bambu CLI slicing, parses
    warnings/errors plus time, mass, layer count, and cost, then retries only
    bounded, known-fix cases.
12. PrintPipe writes the final run report and exits with success only when the
    slice gate passes.

## Acceptance Criteria

### Product-Level Acceptance

- A successful v1 run produces a `.3mf`, repaired mesh, oriented mesh, slice
  report, settings report, logs, previews, and final run report in one run
  folder.
- A successful v1 run opens in Bambu Studio as a Bambu-native project with the
  intended model placement and selected profiles preserved.
- A successful v1 run passes Bambu CLI slicing with no blocker warnings.
- The final report shows input, generated/imported mesh, repaired mesh, bed-fit
  visualization, settings changes, slice summary, warnings, and pre-print
  checklist.
- The slipper proof of concept remains a regression test, but v1 is not
  slipper-specific.

### Input Acceptance

- Still images, GIFs, videos, and existing meshes are accepted through the same
  `printpipe run` command.
- GIF/video runs persist extracted frames, selected references, cleaned frames,
  and a contact sheet.
- Existing mesh import bypasses image-to-mesh generation but still runs repair,
  orientation, bed fit, bundling, slicing, and receipts.

### Mesh Acceptance

- Topology is scanned after mesh generation/import and after repair.
- The repaired mesh must pass watertightness and manifold validation before
  orientation/bundling can be considered successful.
- Repair stats are exported as JSON, including before/after counts for faces,
  non-manifold edges, boundary edges, inverted normals, and repair actions.
- If repair cannot pass validation, the run fails clearly and preserves the
  generated/imported mesh plus repair logs.

### Orientation, Scale, and Bed-Fit Acceptance

- Target real-world size is either supplied by the user or explicitly requested
  before the run proceeds.
- The object is scaled, oriented, rotated if needed, and dropped to the bed using
  recorded transforms.
- Bed-fit validation uses the selected Bambu printer bed dimensions.
- If the model cannot fit without violating the user's size intent, the run
  fails or asks for a permitted scale-down decision before final bundling.
- GUI-safe placement is required; CLI-only bed coordinates are not enough.

### Printer and Filament Acceptance

- V1 loads Bambu printer profiles and Bambu/Orca-compatible filament defaults.
- Material families include PLA, PETG, TPU, ABS/ASA, PC, and PA.
- The settings engine records every override as: setting key, inherited/default
  value, custom value, category, and reason.
- Enum-valued settings are validated before bundling so invalid values cannot be
  silently replaced by Bambu Studio.
- TPU 90A, PLA, and PETG each have at least one dogfood test run before beta.

### 3MF Acceptance

- The `.3mf` includes the model, printer profile, filament profile, process
  profile, Bambu-compatible metadata signature, and bed transform.
- PrintPipe validates the `.3mf` archive structure and required metadata before
  delivery.
- A geometry-only `.3mf` that drops profiles or placement is a failed run.

### Slice-Gate Acceptance

- Bambu CLI slicing is mandatory for success.
- The slice report includes at least status, warnings/errors, time, filament
  mass, layer count, and estimated cost when available.
- Known blocker cases trigger bounded retry or failure: non-manifold geometry,
  off-bed placement, enum replacement, floating/cantilever support failure, and
  missing profile data.
- The user does not receive a successful bundle until the slice gate passes.

### UX Acceptance

- `printpipe run <input>` starts a run.
- `printpipe status` shows current or recent run state.
- `printpipe open-report` opens the HTML report for a run.
- The HTML report is local, readable without a server account, and links to the
  run artifacts.

### Regression Acceptance

- Dogfood objects include slipper, simple figurine, cup/vase, flat bracket or
  wrench-like object, decorative organic object, and existing STL import.
- Every collected beta failure becomes a regression fixture or documented
  unsupported case.

## Failure Criteria

A run must be marked failed if any of these occur:

- Required input, printer, filament, or target-size intent is missing and cannot
  be resolved.
- All mesh generation/import providers fail.
- Mesh repair cannot produce a valid repaired mesh.
- The object cannot be made to fit the selected Bambu bed under allowed scale
  rules.
- Profile enum validation fails.
- The `.3mf` is missing Bambu-native metadata, profiles, model data, or a
  GUI-safe transform.
- Bambu CLI slicing fails or reports blocker warnings.
- The app cannot write a complete run report and receipts.

A failed run is acceptable only if it preserves enough artifacts and logs to
diagnose the failure.

## What Receipts Must Prove

Every run folder is the audit trail. Receipts must prove:

- Which original input was used.
- Which frames or mesh source drove the result.
- Which mesh provider ran, including retries, fallback attempts, time, cost, and
  provider errors.
- What topology defects existed before repair and what changed after repair.
- That the repaired mesh passed validation.
- What orientation, scale, bed transform, and bed-fit decision were applied.
- Which Bambu printer, filament, and process profiles were used.
- Which settings changed, what they inherited from, and why each change exists.
- That enum values were validated before bundling.
- That the `.3mf` contains the expected model, profiles, metadata, and transform.
- That Bambu CLI slicing ran, with parsed warnings/errors, time, mass, layer
  count, and cost where available.
- Whether the final result is `success` or `failed`, with the exact failed gate.

## Roadmap Coverage

This requirements document defines acceptance for these roadmap items:

- Phase 0, items 1-6: v1 local-first scope, Bambu-only launch, supported inputs,
  supported outputs, one-shot acceptance, and slice-verified success.
- Phase 1, items 7-15: repo/project setup is treated as an already-complete
  prerequisite. This document assumes the private repo, `printpipe` codename,
  Python-first stack, project structure, tests, README, architecture doc, and run
  artifact convention exist; it does not add new product acceptance beyond those
  foundations.
- Phase 2, items 16-23: extraction requirements for reusable slipper pipeline
  pieces and slipper-specific assumptions.
- Phase 3, items 24-34: run folder and receipt artifacts.
- Phase 4, items 35-43: image/GIF/video input processing.
- Phase 5, items 44-50: mesh-generation provider interface, import provider,
  retries, failure logging, and cost/time tracking.
- Phase 6, items 51-58: mesh topology scan, repair, validation, repair stats,
  and clear repair failure.
- Phase 7, items 59-66: object understanding and internal orientation
  candidates.
- Phase 8, items 67-73: target size, scale, bed dimensions, rotate/scale/fail
  policy, drop-to-bed, and visualization.
- Phase 9, items 74-81: Bambu printer/filament profile loading, material
  families, override rules, enum validation, settings delta, and reasons.
- Phase 10, items 82-89: Bambu-native `.3mf` bundling and validation.
- Phase 11, items 90-95: Bambu CLI slice gate, parsing, retry/fail rules,
  slice logs, and final slice report.
- Phase 12, items 96-102: local CLI/report UX for verification.
- Phase 13, items 103-112: dogfood object and material acceptance matrix.
- Phase 14, items 113-120: local UI requirements are covered as a later v1
  surface that must call the same pipeline and expose the same artifacts.
- Phase 15, items 121-125: packaging requirements are covered at the acceptance
  level for macOS/Windows and local Bambu dependency detection. Item 126 is
  explicitly not v1.
- Phase 16, items 127-134: beta criteria are covered as regression and feedback
  acceptance.

This document does not define v1 acceptance for Phase 17, items 135-142, except
to preserve item 142's principle that the local app remains the power-user
version. Hosted mesh generation can be used as a provider, but hosted product
infrastructure is not part of v1.
