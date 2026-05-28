# PrintPipe UI/UX Command Center Waves

## Wave 1: Full UI/UX Audit

### Current Screens And Routes

- `/` renders the local home screen with new-run upload controls, printer/material/target size inputs, recent runs, service health, and static local pages.
- `POST /runs` creates a run. Mesh inputs use the existing-mesh pipeline; media inputs create reference artifacts and either run configured Hunyuan3D meshgen or carry explicit provider-configuration failure receipts.
- `/runs/<id>` renders the live run-detail workbench from `build_run_detail()`: topbar, print verdict strip, model workbench, edit/rebuild form, artifact tiles, pipeline stages, validation results, and preview image when available.
- `POST /runs/<id>/edits` creates a non-destructive child edit run using the existing edit recipe contract and redirects to the child run.
- `/runs/<id>/artifacts/<path>` safely serves local artifacts.
- `/static/<path>` serves generated report/static HTML pages.
- `/health` returns JSON service status.

### Current Strengths

- The app has a real local-first web spine without frontend framework overhead.
- The run-detail contract separates UI needs from pipeline internals: verdict, validation, pipeline, artifacts, warnings, geometry, parent run, and edit recipe.
- The workbench already answers the basic printability question and keeps rebuild controls close to artifacts.
- Artifact URLs are safe and ordered by product importance.
- Deterministic SVG/bounds previews are honest about what is known.
- Edit runs are non-destructive, which matches the product requirement to iterate without losing evidence.

### Gaps And Flat Spots

- The route is currently very dense in one long server file. UI changes are possible, but the file is approaching the point where extracting render helpers would reduce risk.
- The top verdict is strong, but failed-state explanations still rely on generic validation messages. The page should name the blocker more directly: meshgen unavailable, repair failed, bed fit failed, slice crashed, support risk unresolved, or artifact missing.
- Parent/child edit context is present in data but underused visually. Users need to know what changed from the previous attempt.
- Empty and missing-artifact states are technically handled, but not yet product-polished. Missing previews, missing bundles, and missing reports should feel intentional rather than broken.
- Prompt-only and unconfigured-media failure states need a better UI treatment because those are expected current limitations, not surprising crashes.
- Pipeline receipts are useful but secondary; they should support the verdict rather than visually compete with model/edit/action.

### Missing Or Underdesigned States

- Empty state: no runs yet, no local pages, no artifacts yet.
- Loading/running state: not a major current stdlib use case, but progress states exist and need a design if long-running meshgen arrives.
- Failed media meshgen: media inputs now fail explicitly when the Hunyuan3D command is not configured; UI should explain "reference captured, meshgen provider unavailable" and make the next setup step clear.
- Failed repair: should show topology evidence and stop-before-bundle confidence.
- Failed slice: should show first classified Bambu error, logs, and whether 3MF is still safe to inspect.
- Print-ready: should emphasize "Open 3MF / inspect slice / print coupon first" rather than rebuild.
- Support-risk: should present support strategy as the next action.
- Bed-fit issue: should prioritize scale/rotate/target dimensions.
- Edit-child run: should show parent run, edit recipe, changed values, and whether current child output supersedes parent.
- Artifact missing: should show missing but expected artifacts with likely reason.

## Wave 2: Product Information Architecture

### Ideal Navigation

- Home / Runs
  - New run form
  - Recent runs list with verdict, progress, warnings, and primary action
- Run Detail / Workbench
  - Verdict and next action
  - Model/bed preview
  - Edit/rebuild controls
  - Artifacts
  - Validation and warnings
  - Pipeline receipts
  - Parent/edit history when available
- Generated Report
  - Current static report remains useful as printable/shareable evidence.
- Artifact Download
  - Safe direct artifact route.
- Service / Doctor
  - Health and future dependency checks.

### Main User Flows

1. Create run from STL
   - User uploads mesh, selects printer/material/target.
   - Needs: upload validation, selected profile, run id, route to workbench/report.
   - Backend exists for existing mesh path.

2. Create run from image/GIF/video
   - User uploads reference media.
   - Needs: honest "reference captured, meshgen unavailable" state when `PRINTPIPE_HUNYUAN3D_COMMAND` is unset.
   - Backend now writes input/reference artifacts and either continues through configured Hunyuan3D meshgen or records a failed provider-configuration receipt.

3. Create run from prompt only
   - Not currently supported.
   - UI should not imply it is supported until backend exists.

4. Inspect run
   - User lands on `/runs/<id>`.
   - Needs: verdict, blocker, confidence, preview, artifacts, and pipeline evidence.

5. Edit geometry
   - User changes scale/target/opening/arch/wall/support/freeform instruction.
   - Needs: clear statement that semantic edits may be recorded before they are fully applied by geometry backend.

6. Rebuild
   - User submits edit recipe.
   - Needs: non-destructive child run, parent link, changed values, new verdict.
   - Backend exists.

7. Compare versions
   - Needs: parent/child run metadata, edit deltas, artifact comparison, verdict comparison.
   - Backend has parent metadata, but no full visual compare UI yet.

8. Export/send to printer
   - Needs: 3MF link, slice receipt, Bambu/open-folder affordance.
   - Backend has artifact routes; one-click open/send remains future.

### Screen Data Requirements

- Home: recent run statuses, artifact availability, report link, workbench link, run progress.
- Run detail: `build_run_detail()` payload, artifact links from discovery, warning list, parent run metadata, edit recipe, geometry metrics.
- Compare versions: parent run detail, child run detail, edit recipe diff, artifact presence.
- Failure/debug view: pipeline stages, warnings, first classified error, logs/artifact links.

## Wave 3: Design System Direction

### Component Patterns To Borrow

- Verdict strip: ReUI-style dashboard stat cards, but with one large command-center card.
- Run timeline: Fusion/ComfyUI-inspired execution history, compact and secondary.
- Pipeline receipts: Vercel/Sentry style status rows with message, artifact, and failure reason.
- Artifact browser: Hugging Face/MakerWorld style file list, with product labels and compatibility emphasis.
- Edit panel: Figma/Rhino properties panel, persistent and plain.
- Version comparison: Onshape/Fusion history idea, parent -> child lineage with changed fields.
- Mesh/bed preview: Bambu/Prusa slicer-style view modes: model, bed fit, line/support/slice.
- Warnings/errors: Sentry event highlights plus slicer notification language.
- Settings summaries: MakerWorld print-profile metadata: printer, filament, size, supports, time, mass.

### PrintPipe Design Language

- Spacing: 8px base rhythm. Use 12-16px panel padding, 10-14px gaps, 18-24px page padding.
- Typography: system sans for UI, system monospace for run ids, artifact paths, stage keys, and measurements.
- Color roles:
  - Ink/background: cool neutral, not marketing bright.
  - Pass: green for validated gates only.
  - Warn/review: amber for unresolved risk.
  - Fail/blocked: red for action-required failure.
  - Action: blue for rebuild/open/download actions.
- Card/panel rules:
  - One visual boundary per region.
  - Avoid nested cards inside cards; use rows, dividers, and strips.
  - Preview/editor/artifact are primary; pipeline/logs are supporting.
- Button hierarchy:
  - One primary action per run state.
  - Secondary actions are links or outline buttons.
  - Dangerous or blocked states should not use green.
- Icon usage:
  - Optional only. If added, keep icons functional: pass/warn/fail, artifact type, download/open.
  - Do not rely on icon-only actions.

## Recommended North Star

PrintPipe should feel like a local AI-to-print command center: Bambu Studio's seriousness, Linear's focus, Sentry/Vercel's failure clarity, Figma/Rhino's inspect-panel workflow, and Replicate's input/output/run-object honesty. The UI should never overclaim geometry intelligence the backend does not have yet.
