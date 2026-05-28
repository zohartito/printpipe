# Wave 118 - Final Next-Action Artifact Visibility

## Purpose

`final-plan` had the right ordered next command, but the top-level `next_action` dropped the supporting files that make the action executable. For the current physical PLA gate, that meant the command was visible while the coupon STL, coupon JSON sidecar, and print handoff were only visible lower in the section action list.

## What changed

- `final-plan` now copies supporting paths from the selected action into top-level `next_action`.
- Supported keys:
  - `coupon_stl_path`
  - `coupon_json_path`
  - `handoff_markdown_path`
  - `report_path`
  - `bundle_path`
- The home-page `Final readiness / Remaining actions` next-action callout now renders those paths when present.

## Verification

- `pytest tests/test_final_plan.py::test_final_action_plan_next_action_keeps_handoff_and_artifact_paths tests/test_final_readiness_web.py::test_render_final_readiness_panel_includes_honest_boundaries -q`
- `printpipe final-plan --release-dir dist/release --runs-dir runs --regression-manifest regressions/dogfood_failures.json --json`

## Boundary

This wave only improves execution visibility. A visible coupon path is not a printed coupon, a visible handoff path is not evidence, and a visible report or bundle is not trusted-user approval.
