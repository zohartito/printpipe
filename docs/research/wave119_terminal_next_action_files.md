# Wave 119 - Terminal Next-Action File Visibility

## Purpose

Wave 118 made `final-plan --json` and the home-page final-readiness callout carry supporting files for the immediate next action. The plain terminal renderer still printed only the command, which made the current physical PLA action less useful from the CLI than from JSON or the web UI.

## What changed

- `render_final_action_plan()` now prints next-action supporting paths under the command.
- Terminal labels:
  - `artifact` for `coupon_stl_path`
  - `sidecar` for `coupon_json_path`
  - `handoff` for `handoff_markdown_path`
  - `report` for `report_path`
  - `bundle` for `bundle_path`

## Verification

- `pytest tests/test_final_plan.py::test_render_final_action_plan_lists_next_action_supporting_paths -q`
- `printpipe final-plan --release-dir dist/release --runs-dir runs --regression-manifest regressions/dogfood_failures.json`

## Boundary

This is CLI visibility only. The physical validation gate still requires real printed PLA, PETG, and TPU evidence packets with existing photo files and observations.
