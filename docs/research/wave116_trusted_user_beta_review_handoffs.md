# Wave 116 - Trusted-User Beta Review Handoff Sheets

## Purpose

The trusted-user beta gate already had packet writing, status scanning, action planning, and strict completed-feedback semantics. The gap was operational: a tester still needed a single handoff sheet that connected the run report, bundle, review instructions, proof boundary, and later `record-beta-feedback` command.

## What changed

- Added `printpipe beta-feedback-start <run-root>`.
- Added `start_trusted_user_feedback()` in the trusted-feedback helper layer.
- `beta-feedback-start --json` returns:
  - `handoff_markdown_path`
  - `report_path`
  - `bundle_path`
  - `record_command`
- Non-JSON `beta-feedback-start` prints the report, bundle, review handoff path, and later record command.
- `beta-feedback-plan` now includes a `start_command` for each missing trusted-user slot.
- `beta-feedback-plan` surfaces existing trusted-user handoff paths when they exist.

## Handoff sheet contents

Each handoff sheet includes:

- run folder
- input type
- material
- printer
- run report path
- `.3mf` bundle path when present
- tester name
- review instructions
- exact `record-beta-feedback` command to run after review
- proof boundary that only completed trusted-user feedback packets count

## Local evidence generated

Ignored local handoff sheets now exist for the slipper proof run:

- `runs/20260528-042826-slipper-size11-v2c-wide-upper-textured/90_beta/trusted_user_feedback_handoff_trusted-user-1.md`
- `runs/20260528-042826-slipper-size11-v2c-wide-upper-textured/90_beta/trusted_user_feedback_handoff_trusted-user-2.md`
- `runs/20260528-042826-slipper-size11-v2c-wide-upper-textured/90_beta/trusted_user_feedback_handoff_trusted-user-3.md`

## Verification

- `pytest tests/test_beta_feedback.py -q`
- `printpipe beta-feedback-start runs/20260528-042826-slipper-size11-v2c-wide-upper-textured --tester trusted-user-1 --input-type existing_stl --material "SUNLU TPU 90A" --printer "Bambu Lab P2S" --json`
- `printpipe beta-feedback-start runs/20260528-042826-slipper-size11-v2c-wide-upper-textured --tester trusted-user-2 --input-type existing_stl --material "SUNLU TPU 90A" --printer "Bambu Lab P2S" --json`
- `printpipe beta-feedback-start runs/20260528-042826-slipper-size11-v2c-wide-upper-textured --tester trusted-user-3 --input-type existing_stl --material "SUNLU TPU 90A" --printer "Bambu Lab P2S" --json`
- `printpipe beta-feedback-plan --runs-dir runs`
- `printpipe beta-feedback-status --runs-dir runs --json`

## Boundary

The handoff sheets are not trusted-user feedback. The trusted-user beta gate still requires three unique trusted users with completed `passed`, `failed`, or `partial` feedback packets and no missing required fields.
