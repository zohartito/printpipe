# Wave 1 Validation Strategy

PrintPipe should be validated as a reference-to-print system, not as a mesh
generator. A run is successful only when it produces a repaired, bed-fit,
Bambu-native `.3mf` that slices cleanly and leaves receipts explaining what
happened.

The slipper proof of concept showed the main risk pattern: upstream artifacts
can look plausible while still being unprintable. The v1 strategy therefore
makes topology, Bambu profile validity, Bambu-native 3MF packaging, GUI/CLI bed
placement, and slicer output hard gates.

## Source Lessons

- AI-generated meshes must be assumed broken until scanned and repaired. The
  slipper run had thousands of non-manifold edges until a repair step produced a
  watertight mesh with 0 boundary edges and 0 non-manifold edges.
- Bambu settings are only real if Bambu accepts them. `support_style: organic`
  was silently replaced with `default`; enum validation must happen before
  bundling.
- A `.3mf` can open while discarding the important parts. The Bambu-native
  signature gate must be tested, especially the `Application` metadata and
  project settings config shape.
- Bambu CLI and GUI placement can disagree. The final artifact must use a
  GUI-safe transform, while CLI-only fixtures may need their own bundle.
- Slice estimates are the acceptance boundary. The slipper's useful estimate was
  the v3 CLI/GUI slice with success, no user-facing warnings, 425 layers, about
  21.5 hours, and about 196 g of TPU.
- Failed runs are assets. Every blocker from the slipper project should become a
  named fixture or regression case.

## Test Pyramid

Validation should be layered so most failures are caught before expensive mesh
generation or Bambu slicing.

```text
Manual physical checks
  - Coupon prints, beta feedback, support removal, material feel.

End-to-end slice gates
  - Full run folder, Bambu-native .3mf, Bambu CLI slice, parsed report.

Artifact integration tests
  - Mesh repair chain, orientation/bed fit, profile merge, 3MF bundle validation.

Contract and fixture tests
  - Meshgen provider interface, Bambu schema/enums, run receipts, parsers.

Unit tests
  - Pure geometry helpers, path/run-folder logic, profile delta normalization,
    warning classifiers, CLI argument behavior.
```

Current tests cover only the CLI foundation: `--version` and `init-run` creating
a run root from an existing input. As phases land, tests should move down the
pyramid first. The Bambu CLI slice gate is intentionally higher in the pyramid:
it should run on curated fixtures and release candidates, not on every tiny unit
test.

## Fixture Plan

Keep fixtures small, named, and tied to the gate they exercise. Large real-world
artifacts can live outside the normal test path with manifests and hashes, but
each failure still needs a minimal reproducible fixture in the repo when
possible.

Recommended layout:

```text
tests/fixtures/
  inputs/
    stills/
    gifs/
    videos/
    existing_meshes/
  meshes/
    valid/
    invalid_nonmanifold/
    invalid_boundary_edges/
    invalid_normals/
    invalid_degenerate_faces/
    bed_fit/
    support_risk/
  bambu/
    profiles/
    three_mf/
    slice_logs/
    schemas_or_enum_snapshots/
  regressions/
    YYYY-MM-DD-short-failure-name/
      manifest.json
      README.md
      minimized_input_or_artifact
      expected_failure.json
```

Core synthetic fixtures:

- A watertight cube or calibration part that should pass all topology gates.
- An open box with boundary edges.
- A bow-tie or duplicated-edge mesh that reports non-manifold edges.
- A mesh with inverted normals and negative volume.
- A too-large object that requires rotation or fails bed fit.
- A floating-cantilever object that forces support handling or orientation retry.
- A valid profile pair and an invalid enum profile using the historical
  `support_style: organic` failure.
- A Bambu-native `.3mf` that should pass validation and a foreign/geometry-only
  `.3mf` that should fail the Bambu-native gate.
- Representative Bambu CLI result/log fixtures for success, non-manifold,
  off-bed, enum replacement, and floating-cantilever warning cases.

Core real fixtures:

- Slipper source input and final known-good receipts, preferably as an external
  artifact set with a manifest if file size is high.
- The repaired slipper mesh topology stats: watertight, 0 boundary edges,
  0 non-manifold edges, bed-dropped to `Z=0`.
- The v3 slice outcome shape: success, empty user-facing warning message,
  approximately 21.5 hours, approximately 196 g TPU, 425 layers.
- At least one fixture each for figurine, cup/vase, bracket/wrench-like object,
  decorative organic object, and existing STL import.

Every fixture should include an expectation file rather than implicit assertions
buried in tests. For example, mesh fixtures should have expected topology counts
or pass/fail labels; slice log fixtures should have expected parsed status,
warnings, time, mass, and layer count.

## Mesh Topology Gates

Topology gates run at least three times:

1. Immediately after mesh generation or existing-mesh import.
2. After repair.
3. After orientation, scale, bed drop, and final export.

Required scan fields:

- Vertex count, face count, bounding box, volume, surface area.
- Watertight status.
- Boundary edge count.
- Non-manifold edge count.
- Degenerate face count.
- Duplicate/unreferenced vertex count after cleanup.
- Normal consistency and signed volume direction.
- Euler characteristic for diagnostics, not as a universal pass/fail rule.
- `z_min` after bed drop.
- Printer-specific XY footprint after final orientation.

Default pass criteria for a printable mesh:

- Watertight is true.
- Boundary edge count is 0.
- Non-manifold edge count is 0.
- Degenerate face count is 0 after cleanup.
- Volume is positive and finite.
- Normals are consistently outward after repair.
- The object is bed-dropped, with `z_min` within tolerance of 0.
- The final XY footprint fits the selected printer bed with configured margins.

Repair must produce a `repair_stats.json` receipt with before/after topology,
tools attempted, tools that changed the mesh, and any remaining defects. If the
repair chain cannot satisfy the pass criteria, the run must fail clearly before
orientation, profile generation, or bundling.

No phase should rely on visual plausibility. The slipper mesh looked usable
before repair but was rejected by Bambu because the topology was invalid.

## Bambu Profile And 3MF Gates

Profile validation and 3MF validation are separate gates.

Profile gates:

- Load printer, filament, and process profiles from known Bambu/Orca-compatible
  sources or curated snapshots.
- Validate enum values against Bambu source/schema snapshots before bundling.
- Normalize scalar/list and numeric-string formatting before diffing profiles.
- Require a reason for every behavior-changing setting delta.
- Separate behavior changes from metadata and formatting-only normalization.
- Verify Bambu-required identity fields exactly, including case-sensitive fields
  such as `from: "User"` where applicable.
- Reject unknown enum replacements instead of trusting Bambu Studio to downgrade
  them.
- Record profile source, inherited defaults, overrides, and reasons in the run
  report.

Historical profile regression cases:

- `support_style: organic` must fail validation; valid values for the targeted
  Bambu Studio generation should include `default` and `snug`.
- TPU support settings must be slice-tested, not assumed self-supporting.
- Brim gaps, pressure advance, seam position, shell count, and first-layer
  temperature changes should appear in the settings delta with reasons.

3MF gates:

- The `.3mf` zip must contain the model, printer profile, filament profile,
  process profile, project settings, and required metadata.
- The Bambu-native detection metadata must be present. In the slipper proof,
  Bambu accepted bundles only after the `Application` metadata started with
  `BambuStudio-` and `project_settings.config` had the expected project fields
  and dotted-quad version shape.
- The bundle must preserve custom profiles instead of loading geometry only.
- The model transform must be GUI-safe. If the CLI needs a special placement
  bundle, keep it separate from the user-facing GUI bundle.
- The final model must be on the selected bed, not merely accepted by one Bambu
  entry point.
- The bundle must not contain absolute local paths or stale artifacts from prior
  runs.
- 3MF validation should produce a manifest listing files, profile names, profile
  hashes, model hashes, transform, selected printer, selected filament, and
  Bambu-native status.

The gate passes only when profile validation and 3MF manifest validation both
pass. Opening in Bambu Studio is useful evidence, but it is not a replacement
for machine-checked profile and manifest validation.

## Slice Gate Expectations

The slice gate is the main acceptance gate for v1.

Inputs:

- The Bambu-native `.3mf`.
- Selected printer, bed, nozzle, filament, and process profile identifiers.
- Bambu Studio CLI path and version.
- Run folder output path.

Required outputs:

- Raw slicer result JSON if available.
- Raw slicer stdout/stderr logs.
- G-code or explicit reason no G-code was emitted.
- Parsed slice summary: return code, success flag, time, mass, filament length,
  layer count, max Z, object bounding box, warnings, errors, and cost estimate.
- A final slice report in Markdown or HTML.

Pass criteria:

- Bambu CLI returns success.
- G-code is generated.
- User-facing warning message is empty, or every warning is in a narrow
  documented allowlist with an issue link and rationale.
- No non-manifold, boundary-edge, off-bed, enum-replacement, missing-profile, or
  floating-cantilever warning is allowed.
- Parsed object bbox fits the selected bed and has `z_min` at the bed.
- Parsed time, mass, layers, and cost are written to the run report.
- Estimates are refreshed whenever geometry, supports, shell count, infill,
  material, profile overrides, or orientation changes.

Retry expectations:

- Non-manifold or boundary-edge failures go back to repair.
- Off-bed failures go back to orientation, scale, bed fit, or GUI/CLI transform
  handling.
- Floating-cantilever failures go back to orientation scoring and support rules.
- Enum replacement failures go back to Bambu profile validation.
- Missing-profile or geometry-only load failures go back to 3MF bundling.

Internal noisy log lines can be classified separately only when the slicer
returns success, emits G-code, and has no user-facing warning message. The
slipper v3 `ZFiller` lines are the model for this policy: document them, do not
hide them, and do not let them mask real slicer warnings.

## Regression Policy From Failed Runs

Every failed run becomes a regression item before the fix is considered done.

Policy:

- Preserve the run folder or a minimized reproduction.
- Add a `manifest.json` with input hash, command, platform, Bambu Studio
  version, printer, filament, provider, random seed if any, artifact hashes,
  first failing gate, observed message, and expected future behavior.
- Classify the failure as one of: input, meshgen, repair, orientation, bed fit,
  profile, 3MF, slice, report/UX, packaging, or physical print.
- Add the smallest automated test that would have caught the failure.
- If the artifact is too large for normal git, store a redacted or minimized
  fixture in git and reference the full artifact by path/hash in the manifest.
- Do not close the issue by suppressing warnings. Either fix the cause or add a
  narrow, documented allowlist entry with an owner and rationale.
- Keep the fixture after the fix lands.

Regression tests should fail for the historical slipper blockers:

- Generated mesh with thousands of non-manifold edges reaches bundling without
  repair.
- GUI-safe placement differs from CLI-only placement and causes an off-bed GUI
  bundle.
- `support_style: organic` reaches Bambu and is replaced.
- A foreign `.3mf` opens as geometry-only and loses embedded settings.
- A no-support assumption produces a floating-cantilever slicer warning.
- A stale settings report claims changes without normalized diffs and reasons.

Beta policy:

- During Phase 16, every dogfood or user failure gets a regression item within
  one working session.
- Material, orientation, and repair rules are updated only after the failed run
  has an artifact-backed reproduction.
- Physical print failures, such as TPU support removal or flex feel, can be
  logged as manual regressions with coupon photos/notes even when they cannot be
  fully automated.

## Roadmap Phase Done Criteria

No roadmap phase is done just because it generated an artifact. A phase is done
when its artifacts satisfy the relevant gates and its failure modes have tests or
documented manual checks.

| Phase | Required verification before done |
|---|---|
| Phase 0 - Product Ground Rules | Scope is documented as local-first, Bambu-only for launch, supported inputs/outputs are named, success is defined as slice-verified, and no roadmap or README text contradicts that boundary. |
| Phase 1 - Repo and Project Setup | Clean install works, `pytest` passes, `printpipe --version` works, `init-run` creates a run root from an existing input, architecture/roadmap docs exist, and run artifact conventions are documented. |
| Phase 2 - Extract the Slipper Pipeline | Slipper scripts are inventoried, reusable pieces are ported behind PrintPipe module boundaries, slipper-specific assumptions are removed or parameterized, and golden tests cover repair, 3MF bundling, settings delta, and slice parsing using slipper-derived fixtures. |
| Phase 3 - Run Folder and Receipts System | Each run creates an immutable folder with manifest and hashes; original input, frames, generated/repaired/oriented mesh, profiles, `.3mf`, slice logs, previews, and final report have deterministic locations; tests verify missing and partial artifacts are reported clearly. |
| Phase 4 - Input Processing | Still image, GIF, and video fixtures produce selected references, cleaned frames, normalized images, and contact sheets; corrupted or unsupported inputs fail before meshgen with clear receipts. |
| Phase 5 - Mesh Generation Providers | Provider interface contract tests pass; Hunyuan3D and existing-mesh import are covered by mocks/fixtures; retries, failures, cost/time tracking, and provider logs are recorded without requiring a live cloud service in unit tests. |
| Phase 6 - Mesh Repair and Validation | Topology scan runs before and after repair; repaired fixtures pass watertight, boundary, non-manifold, normal, volume, and bed-drop checks; irreparable fixtures fail clearly with `repair_stats.json`; slipper non-manifold regression is covered. |
| Phase 7 - Object Understanding | Bounding box, primary axes, flat-base detection, cavity/opening notes where supported, and top-three orientation candidates are deterministic on fixtures; orientation choices do not assume support-free printing without slice evidence. |
| Phase 8 - Scale and Bed Fit | Target size application, P2S bed dimensions, rotate-to-fit, scale-down/fail policy, bed drop, and bed-fit visualization are tested; GUI-safe and CLI-safe placement behavior is explicitly verified. |
| Phase 9 - Printer and Filament Engine | Printer and filament defaults load; material-family override rules are tested; enum values are validated against Bambu source/schema snapshots; normalized settings deltas include reasons for every behavior change. |
| Phase 10 - 3MF Bundling | Bambu-native `.3mf` bundles contain model, printer, filament, process, metadata, project settings, and GUI-safe transform; manifest validation passes; invalid/foreign bundles fail; custom profiles are preserved rather than loaded as geometry-only. |
| Phase 11 - Slice Gate | Bambu CLI slice runs on the bundled `.3mf`; result/log parsing extracts warnings, errors, time, mass, layers, cost, bbox, and G-code path; non-manifold, off-bed, enum replacement, and floating-cantilever cases fail or retry through the correct earlier gate. |
| Phase 12 - Verification UX | `printpipe run`, `printpipe status`, and `printpipe open-report` work on fixtures; HTML report shows input, mesh, repaired mesh, bed fit, slice summary, warnings, settings changes, and pre-print checklist; golden report snapshots stay current. |
| Phase 13 - Test Objects | Slipper, figurine, cup/vase, bracket/wrench-like, decorative organic object, existing STL, TPU, PLA, and PETG cases all have expected outcomes; outcomes are compared in a matrix and any failure is converted into a regression. |
| Phase 14 - Local UI | Drag/drop, printer selection, filament selection, target size, progress, previews, and `.3mf` open/download flows are covered by browser smoke tests against local fixtures; UI state matches run receipts and never marks a failed slice as successful. |
| Phase 15 - Packaging | macOS and Windows packages install cleanly, detect Bambu Studio and user profile folders, report missing dependencies clearly, and run a smoke pipeline from a clean user environment. |
| Phase 16 - Beta | Slipper and at least three non-slipper objects are dogfooded; 3 to 5 trusted users run the tool; every failed run becomes a regression; material, orientation, and repair rules are updated from artifact-backed evidence. |
| Phase 17 - Web/Cloud Later | No hosted API, auth, storage, queue, billing, or GPU worker work starts until local slice-verified runs are reliable; cloud paths must preserve the same run receipts, topology gates, Bambu gates, slice gates, and regression policy. |

## Minimum Acceptance For V1

PrintPipe v1 is ready to beta only when the CLI can run at least the Phase 13
fixture matrix and produce, for each passing case:

- A complete run folder with manifest and hashes.
- A repaired and validated mesh.
- A GUI-safe Bambu-native `.3mf`.
- A Bambu CLI slice success with no disallowed warnings.
- A slice report with time, mass, layers, cost, bbox, and settings delta.
- A regression entry for every case that does not pass.

The user-facing promise is not "we generated a mesh." It is "we can show why
this Bambu project is ready to inspect, slice, and print."
