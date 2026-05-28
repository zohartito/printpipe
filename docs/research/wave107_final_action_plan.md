# Wave 107 - Final Action Plan Aggregator

## What Changed

- Added `printpipe final-plan` as the top-level endgame checklist.
- Added `/final-plan.json` for local web and agent automation.
- Added a home-page `Final action plan` panel above the separate release/readiness panels.
- Preserved the source plans instead of replacing them:
  - `physical-plan`
  - `beta-feedback-plan`
  - `release-plan`

## Why

The remaining PrintPipe work is no longer mostly code. It is evidence:

- real PLA, PETG, and TPU physical validation packets
- three trusted-user feedback packets
- signed/notarized macOS distribution artifacts
- a signed Windows installer artifact

The final plan makes that sequence visible in one place without inflating readiness.

## Boundary

A generated final plan is not evidence. It is only an ordered checklist. Gates close only when the underlying evidence packets or verified signed artifacts exist on disk.

## Verification

- `tests/test_final_plan.py`
- `tests/test_web_server.py`
