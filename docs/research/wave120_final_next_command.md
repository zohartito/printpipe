# Wave 120 - Final Next Command

## Purpose

`final-plan` is useful for the full endgame checklist, but the current real next step is only one action: record credible PLA physical validation after a real coupon print. Agents and users should not need to parse the full section list just to find the immediate command and supporting files.

## What changed

- Added `printpipe final-next`.
- Added `render_final_next_action()`.
- `final-next` accepts:
  - `--release-dir`
  - `--runs-dir`
  - `--regression-manifest`
  - `--json`
- `final-next --json` returns:
  - `overall_status`
  - `action_count`
  - `proof_boundary`
  - `next_action`
  - `next_command`

## Verification

- `pytest tests/test_final_plan.py::test_render_final_next_action_shows_only_immediate_action tests/test_final_plan.py::test_final_next_parser_accepts_dirs_json_and_regression_manifest tests/test_final_plan.py::test_cli_final_next_prints_next_action_json -q`
- `printpipe final-next --release-dir dist/release --runs-dir runs --regression-manifest regressions/dogfood_failures.json`

## Boundary

This command is only a focused view of the existing final action plan. It does not record physical evidence, fabricate trusted-user feedback, or sign distribution artifacts.
