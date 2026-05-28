# Wave 134 - Terminal Final Plan Action Details

Status: complete for terminal checklist visibility. This is not external
evidence.

## Problem

`final-plan` had a detailed top `Next action` block, but the section checklist
below it only listed one-line action summaries such as `action_required: macOS
distribution`. That made the terminal output less useful than the web
final-readiness checklist and forced Zohar to call separate plan commands to see
the actual files and commands for non-next actions.

## Change

- Section action rows now render details.
- Rows render required inputs.
- Rows render start/setup/build commands, follow-up checks, and contextual
  record commands.
- Trusted-user rows say `record after review`.
- Physical rows say `record after print`.
- Rows render supporting paths for artifacts, sidecars, handoffs, reports,
  bundles, bundle validations, and slice receipts.

## Verification

- `tests/test_final_plan.py::test_render_final_action_plan_lists_section_action_commands_and_files`

## Boundary

This wave improves terminal handoff clarity only. It does not print coupons,
collect trusted-user feedback, create signing credentials, notarize macOS
artifacts, or sign Windows installers.
