# Wave 14 Next Steps

This is the handoff after Wave 13. The original 142-item roadmap is not complete-complete in the physical/product sense, but the software foundation is much healthier than it was at the start of the slipper recovery.

## Where We Are

Original roadmap status:

- Done: 121 / 142
- Partial: 21 / 142
- Pending: 0 / 142
- Blocked: 0 / 142

What is genuinely working now:

- Existing STL input can run through import, mesh repair, orientation, bed-fit preview, Bambu `.3mf` bundle generation, bundle validation, and reporting.
- Requested live slice runs now have explicit CLI behavior: `printpipe run --slice` invokes Bambu Studio CLI, writes stdout/stderr/slice-result artifacts, keeps report paths visible on failure, and marks missing/crashed slicers as failed requested slice gates.
- Local web upload for STL uses the same pipeline and exposes direct `.3mf` download.
- HTML reports show input, mesh, repair, bed fit, slice summary, warnings, settings changes, previews, and pre-print checklist.
- The test suite passes from a clean `/tmp` checkout.

What is still not proven:

- Successful live Bambu Studio CLI slicing of a freshly generated PrintPipe bundle. Bambu Studio 2.6.00.51 currently segfaults on this machine even when slicing a direct tiny STL, so this is now a Bambu CLI/runtime investigation rather than just a PrintPipe receipt gap.
- Image/GIF/video to mesh to print-ready bundle in the normal orchestrator.
- Physical slipper print, TPU coupon, PLA print, PETG print, and beta-user feedback.
- macOS/Windows packaged app install from a clean user environment.

## Findings To Add

Wave 13 found two practical issues that should become roadmap work:

- macOS privacy/TCC can make a Desktop checkout visible to `stat` but unreadable to shell Python and git. The app should diagnose this clearly instead of failing mysteriously.
- Browser verification found a home-page crash when recent-run scanning touched unreadable paths. That specific crash is fixed, but the broader permission class deserves a doctor check.
- Bambu Studio CLI `--slice` is syntactically valid in 02.06.00.51, but it exits with signal 11 on macOS 26.5. The crash stack points at `Slic3r::DynamicPrintConfig::update_values_to_printer_extruders_for_multiple_filaments`, after `Print::update_filament_maps_to_config`.

The new backlog lives in `docs/APP_ROADMAP.md` under "Post-Wave 13 Findings Backlog" as F1-F13. These items are intentionally outside the original 142 count. F3 is complete; F13 captures the local Bambu CLI crash uncovered while proving F3.

## Wave 14 Progress

F3 is complete as a PrintPipe feature:

- `--bambu-cli` is rejected unless `--slice` is also set.
- `--slice` is rejected for direct image/GIF/video inputs; Wave 23 now wires those inputs through configured Hunyuan3D meshgen before bundling.
- Missing Bambu CLI is now a failed requested slice gate, not a skipped not-requested gate.
- CLI pipeline failures print the run folder and report paths before returning nonzero.
- Slice receipts include `slice_requested=true`, command, executable, checked candidates, logs, return code, warnings, errors, and parsed estimates when G-code is produced.
- Negative subprocess return codes are reported as signals, for example `slicer terminated by signal 11 (SIGSEGV)`.

Live probe result:

```text
/Applications/BambuStudio.app/Contents/MacOS/BambuStudio --slice 0 --outputdir <dir> <file>
return code: -11
classification: slicer terminated by signal 11 (SIGSEGV)
GUI hang: no
leftover BambuStudio process: no
```

This happened for both a PrintPipe-generated `.3mf` and a direct tiny STL fixture.

## Recommended Next Wave

Wave 14 should target the highest-risk truth boundary: can PrintPipe generate a Bambu bundle and get a real slice receipt without handwaving?

Recommended six subagents:

1. Bambu CLI segfault agent: isolate whether the 02.06.00.51 crash is caused by macOS 26.5, missing CLI settings, P2S profile loading, or a Bambu Studio regression; find a non-crashing invocation or document that GUI/manual slice is the current workaround.
2. Permission/doctor agent: own macOS Desktop/TCC diagnostics, unreadable workspace tests, and clearer user instructions.
3. Hunyuan orchestration agent: wire image/GIF/video provider output into the same repair/orient/bundle path used by existing STL.
4. Preview/render agent: produce deterministic mesh/bed/report screenshots or rendered previews that can live in run folders.
5. Flex coupon agent: generate a 30-50 mm TPU coupon STL and bundle/report path using the same material settings assumptions.
6. Docs/status agent: update evidence docs, roadmap counts, and beta handoff templates after the other five land.

## After Wave 14

If Wave 14 succeeds, Wave 15 should be physical validation:

- Print flex coupon first.
- Slice and inspect slipper bundle.
- Print slipper only after coupon and layer preview are clean.
- Run one PLA and one PETG small object.
- Convert every failure into a regression before changing material or geometry rules.

## Verification Baseline

Latest verified baseline:

```text
.venv/bin/python -m pytest
263 passed, 2 skipped
```

The two skips are expected in this environment:

- Optional dependency/environment branch where applicable.
- External slipper artifact hash check when macOS denies read access under `~/Desktop`.
