# PrintPipe UI/UX Wave Recommendation

## Chosen Direction

Ship a serious **AI-to-print command center** built around three layers:

1. Verdict and next action.
2. Model/bed workbench with edit/rebuild controls and nearby artifacts.
3. Receipts, warnings, and version history as supporting evidence.

The live app already follows much of this direction. The next work should refine state clarity, not replace the route wholesale.

## What To Copy From The Prototypes

- From `run-detail-full-a-print-ready.html`: print-ready handoff language, "Open 3MF / inspect slice / coupon first" action hierarchy, and confidence summary.
- From `run-detail-full-b-failure-states.html`: explicit failed media meshgen and slice crash explanations. These are product states, not generic errors.
- From `run-detail-full-c-version-compare.html`: parent/child run context, edit deltas, and "what changed" summary.
- From earlier Direction B: central model/bed preview and right-side edit panel.
- From earlier Direction A: compact command-center verdict and one primary next action.

## What To Avoid

- Do not turn the route into a full CAD app before real GLB/STL rendering exists.
- Do not use nested cards for every detail.
- Do not make failed media inputs look like unexpected crashes; they are known provider-configuration states when Hunyuan3D is unavailable.
- Do not bury artifacts below long receipt tables.
- Do not add React/Tailwind/shadcn just to mirror ReUI examples.

## Phased Implementation Plan

### Phase 1: State Clarity In Existing Route
- Add a version/context strip under the verdict when a run is a child edit.
- Surface warning count and first warning near the verdict.
- Keep the existing workbench layout and form contracts.
- Files: `src/printpipe/web/server.py`, `tests/test_web_server.py`.

### Phase 2: Failure-State Copy And Receipts
- Improve copy for failed media meshgen, failed repair, failed slice, artifact missing.
- Keep backed by current `build_run_detail()` and report warnings.
- Files: likely `src/printpipe/web/server.py`, focused tests.

### Phase 3: Compare Parent/Edit Runs
- Add a lightweight parent-child summary.
- Only build full visual compare after parent and child previews are both reliably discoverable.
- Backend-neutral until richer comparison data exists.

### Phase 4: Rendering Upgrade
- Add real interactive GLB/STL viewer only after a clear dependency decision.
- Until then, keep deterministic SVG/bounds preview honest.

## Risk List

- `server.py` is large. If route rendering grows much more, extract pure render helpers before adding more UI.
- The visual workbench can overclaim geometry knowledge. Keep preview annotations tied to real metrics/warnings.
- Mobile layout can put edit controls before visual context. Use this only on narrow screens.
- Artifact labels and run IDs are long; every artifact tile needs wrapping.
- Failed media meshgen states can frustrate users unless copy explains that references were still captured.

## Exact Files To Touch For First Patch

- `src/printpipe/web/server.py`
- `tests/test_web_server.py`

No need to touch:
- pipeline modules
- mesh generation
- slicer logic
- artifact discovery
- edit recipe behavior
- route names
- form field names
- `build_run_detail()` contract

## Tests To Update

- `tests/test_web_server.py`: assert the new version/context strip and warning summary appear.
- Existing `tests/test_web_artifacts.py` and `tests/test_run_detail_contract.py` should remain unchanged.

## Backend-Neutral Items

- Version-aware text can use current `parent_run`, `edit_recipe`, and `warnings`.
- Warning/action summaries can use current validation and warning data.
- Compare visuals, true support heatmaps, and mesh interaction should wait for rendering/backend support.

## Recommended First Live Upgrade

Implement a narrow **Run Context** strip directly below the verdict:

- For child edit runs: show parent run id, current edit run id, edit delta summary, and first warning.
- For normal runs: show input kind, geometry bounds, warning count, and first warning.
- This answers: "what changed from previous attempt?" and "what should I pay attention to?" without changing backend behavior.
