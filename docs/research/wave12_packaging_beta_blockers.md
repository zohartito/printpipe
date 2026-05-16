# Wave 12 Packaging And Beta Blockers

Status: Wave 12 handoff. This document records what can honestly be marked
software-complete after Wave 12, what is still blocked on user/physical
evidence, and what packaging still requires. Do not use this as evidence that
the slipper or any material family is print-validated.

## Software-Complete After Wave 12

These items have code paths, receipts, or docs/tests that make them usable as
software foundation work:

- Local run folders, manifests, reports, and artifact links.
- Input capture for still images and `ffmpeg`-available GIF/video frame
  extraction.
- Stored extracted, cleaned, and selected reference folders.
- Human-viewable contact-sheet HTML plus JSON manifest.
- Local-command Hunyuan3D provider adapter, disabled unless
  `PRINTPIPE_HUNYUAN3D_COMMAND` is set.
- Geometry helper layer for bounds, primary axes, cavity/opening diagnostics,
  scale planning, scale-down/fail decisions, top orientation candidates, and
  bed-fit SVG/JSON previews.
- Oriented ASCII STL artifact writer for simple STL inputs.
- Optional `trimesh` mesh-repair extra plus repair stats receipts.
- Bambu/Orca profile-root discovery without hardcoded user IDs.
- Bambu Studio CLI executable discovery and slice-command construction.
- Slice-result receipts, stdout/stderr artifacts, optional G-code artifact
  recording, and warning/error classification.
- Local web `POST /runs` upload path that creates a run, prepares inputs,
  writes reports, and redirects to the HTML report.
- Local web artifact grouping with direct `.3mf` download links when bundles are
  present.
- Beta docs, failure template, issue templates, and regression-manifest helper.

## Still Partial In Software

These should stay partial until the named capability is real in the normal
pipeline, not only available as a helper or placeholder:

| Area | Current state | Needed to mark complete |
| --- | --- | --- |
| Mesh repair in normal run | Optional `trimesh` path and receipt wrapper exist; this local venv has the extra installed and tests exercise the repair path. | Regular `printpipe run` invokes repair on generated/imported meshes and uses the repaired mesh downstream. |
| Repaired/oriented mesh storage in normal run | Helpers exist and are tested, but the normal CLI/web flow does not yet drive full meshgen -> repair -> orient -> bundle. | Persist repaired and oriented mesh artifacts from the regular run command. |
| Background removal | Explicit no-op/copy stage with honest metadata. | Real background removal or a documented decision that v1 intentionally does not do it. |
| Lighting normalization | Explicit no-op/copy stage with honest metadata. | Real normalization or a documented decision that v1 intentionally does not do it. |
| Screenshots/previews | Contact-sheet HTML and SVG/JSON bed previews exist. | Capture stable visual previews for input, mesh, bed fit, and slice state in the normal run report. |
| Live Bambu slice in main flow | Slice wrapper/receipts exist. | Regular run invokes Bambu CLI when configured and records a successful slice receipt. |
| Download/open `.3mf` | Web artifact grouping exposes direct `.3mf` download links when bundles exist. | Normal run reliably creates a Bambu-native `.3mf` and exposes it in CLI/web reports. |

## Physical/User-Blocked Items

These cannot be honestly marked done by code alone:

| Roadmap item | Blocker | Evidence required |
| --- | --- | --- |
| Slipper proof of concept | Needs PrintPipe-generated slipper bundle and real print path, not the older external bundle. | Run folder, repaired mesh receipt, oriented bed-fit preview, `.3mf`, slice receipt, Bambu screenshot/layer preview, flex coupon evidence, printed slipper photos, measurements, and failure/pass notes. |
| TPU test | Needs real TPU coupon/part print on target printer and filament. | Spool drying log, printer/nozzle/profile versions, slice receipt, coupon photos, adhesion/flex/stringing/layer-bond notes, and any changed setting deltas. |
| PLA test | Needs real PLA fixture print, not just material rules. | Selected PLA spool/profile, slice receipt, printed part photos, dimensional/adhesion/warping notes, and slicer warnings. |
| PETG test | Needs real PETG fixture print, not just material rules. | Selected PETG spool/profile, slice receipt, printed part photos, adhesion/stringing/warping notes, and slicer warnings. |
| Dogfood with slipper | Needs Zohar/operator run through full pipeline and physical outcome. | Same slipper evidence packet above, plus operator notes about confusing steps. |
| Dogfood with 3 non-slipper objects | Needs at least three object classes run and physically reviewed. | Run folders, slice receipts, print photos, inspection notes, and whether each failure became a regression. |
| Trusted beta users | Needs outside users, not internal fixture tests. | 3-5 feedback bundles with OS, command, doctor JSON, run report, artifacts, screenshots if useful, and confusion/failure notes. |
| Failed-run collection | Needs real failures. | Failure reports tied to run folders and classified by stage. |
| Regression updates | Needs evidence-backed failures. | New fixture or manifest entry plus a test that fails before the fix and passes after. |
| Material/orientation/repair rule updates | Needs real failed or successful prints. | Rule change linked to a beta/dogfood report and before/after behavior. |

## Packaging Requirements

macOS packaging is not complete until all of this is true:

- A launcher/app wraps the same `printpipe` entry point.
- A compatible Python runtime and required dependencies are bundled or installed
  predictably.
- Optional dependencies fail gracefully when omitted.
- Bambu Studio is detected at `/Applications/BambuStudio.app` when present.
- App-shipped profiles are read from the app bundle only; PrintPipe does not
  write into the Bambu Studio app bundle.
- User profiles are detected under
  `~/Library/Application Support/BambuStudio/user/`, preferring numeric user
  directories and falling back to `default`.
- A clean-machine smoke test proves `--version`, `doctor`, `serve`, `run`,
  `status`, and report opening.
- If distributed outside local dev, codesigning/notarization expectations are
  settled before calling it a user package.

Windows packaging is not complete until all of this is true:

- A launcher/app wraps the same `printpipe` entry point.
- A compatible Python runtime and dependencies are bundled or installed
  predictably.
- Bambu Studio install/profile paths are verified on a real Windows machine,
  including `%APPDATA%\BambuStudio\user\`.
- Numeric user directories and `default` fallback behavior are confirmed.
- Path handling works with spaces and backslashes.
- PowerShell setup and clean-machine smoke tests pass.
- The package reports missing Bambu Studio, missing profiles, or missing
  optional deps clearly instead of crashing.

## Verification Commands After Wave 12

Run these from `/Users/zohartito/Desktop/printpipe` before marking the wave
integrated:

```bash
git status --short
git diff --check
.venv/bin/python -m pytest
# 243 passed, 1 skipped on this Wave 12 integration pass
```

Focused beta/packaging checks:

```bash
.venv/bin/python -m pytest \
  tests/test_beta_slipper_dogfood_doc.py \
  tests/test_beta_non_slipper_runs_doc.py \
  tests/test_beta_onboarding_docs.py \
  tests/test_env_macos.py \
  tests/test_env_windows.py \
  tests/test_env_bambu_studio.py \
  tests/test_env_bambu_profiles.py \
  tests/test_env_doctor.py \
  tests/test_cli_doctor.py
```

Manual/local smoke checks when the editable install is active:

```bash
printpipe --version
printpipe doctor
printpipe doctor --json
printpipe run tests/fixtures/objects/existing_stl_pipeline/tiny_tetrahedron.stl --runs-dir runs/wave12-smoke
printpipe status runs/wave12-smoke/<run-id>
printpipe open-report runs/wave12-smoke/<run-id>
printpipe serve --host 127.0.0.1 --port 8765 --runs-dir runs
```

Only run the real Bambu slice gate when Bambu Studio/Bambu CLI is installed and
configured:

```bash
printpipe doctor --json
# Then run the Bambu slice command/path used by the current pipeline and attach
# the resulting slice receipt, stdout/stderr logs, and `.3mf` artifact.
```
