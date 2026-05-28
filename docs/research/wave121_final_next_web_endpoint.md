# Wave 121 - Final Next Web Endpoint

## Purpose

Wave 120 made the immediate final action available through `printpipe final-next`. The local web app still only exposed the full `/final-plan.json`, which forced agents and UI clients to parse the whole checklist to find the next action.

## What changed

- Added shared `build_final_next_action_payload()` in `printpipe.final_plan`.
- Updated `printpipe final-next` to use the shared payload builder.
- Added `/final-next.json` to the local web app.
- Linked `Final next JSON` from the final-readiness panel.
- Kept the payload narrow:
  - `schema_version`
  - `overall_status`
  - `action_count`
  - `proof_boundary`
  - `next_action`
  - `next_command`

## Boundary

This endpoint is a read-only coordination surface. It does not record physical evidence, collect trusted-user feedback, sign installers, or close any release gate.
