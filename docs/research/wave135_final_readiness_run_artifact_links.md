# Wave 135 - Final Readiness Run Artifact Links

Status: complete for web navigation. This is not evidence.

## Problem

The final-readiness web panel showed many useful artifact paths, but they were
plain code text. Run-detail and recent-run cards already use the safe
`/runs/<run-id>/artifacts/...` download route, so final readiness should do the
same when a path clearly points inside a run folder.

## Change

- Top next-action file rows now link paths under `runs/<run-id>/...`.
- Checklist action file rows use the same link behavior.
- Absolute local paths are linked only when they contain a clear
  `runs/<run-id>/...` segment.
- Non-run local paths remain plain text, avoiding arbitrary local-file links.

## Verification

- `tests/test_final_readiness_web.py::test_render_final_readiness_panel_links_run_artifact_paths`

## Boundary

These links only make existing run artifacts easier to open in the local app.
They do not create or validate physical proof, trusted-user proof, or signed
distribution artifacts.
