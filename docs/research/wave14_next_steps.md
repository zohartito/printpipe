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
- Local web upload for STL uses the same pipeline and exposes direct `.3mf` download.
- HTML reports show input, mesh, repair, bed fit, slice summary, warnings, settings changes, previews, and pre-print checklist.
- The test suite passes from a clean `/tmp` checkout.

What is still not proven:

- Live Bambu Studio CLI slicing of a freshly generated PrintPipe bundle.
- Image/GIF/video to mesh to print-ready bundle in the normal orchestrator.
- Physical slipper print, TPU coupon, PLA print, PETG print, and beta-user feedback.
- macOS/Windows packaged app install from a clean user environment.

## Findings To Add

Wave 13 found two practical issues that should become roadmap work:

- macOS privacy/TCC can make a Desktop checkout visible to `stat` but unreadable to shell Python and git. The app should diagnose this clearly instead of failing mysteriously.
- Browser verification found a home-page crash when recent-run scanning touched unreadable paths. That specific crash is fixed, but the broader permission class deserves a doctor check.

The new backlog lives in `docs/APP_ROADMAP.md` under "Post-Wave 13 Findings Backlog" as F1-F12. These items are intentionally outside the original 142 count.

## Recommended Next Wave

Wave 14 should target the highest-risk truth boundary: can PrintPipe generate a Bambu bundle and get a real slice receipt without handwaving?

Recommended six subagents:

1. Live slice gate agent: own Bambu CLI invocation, explicit `--slice` UX, and receipt/error handling against a generated `.3mf`.
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
257 passed, 2 skipped
```

The two skips are expected in this environment:

- Optional dependency/environment branch where applicable.
- External slipper artifact hash check when macOS denies read access under `~/Desktop`.
