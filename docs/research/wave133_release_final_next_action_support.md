# Wave 133 - Release Final Next Action Support

Status: complete for next-action visibility. This is not signed distribution
evidence.

## Problem

Wave 132 made release distribution checklist rows self-contained, but the focused
`final-next` path still only carried the immediate command plus file paths. If
physical validation and trusted-user beta become ready, release distribution
would become the top action and the focused payload would omit the required
signing/tool inputs, actual build/check command, and follow-up verification.

## Change

- `final-plan`/`final-next` next-action payloads now preserve:
  - `required_inputs`
  - secondary `run_command`
  - `followup_command`
- Terminal final-action renderers now print:
  - `required inputs`
  - `run after prerequisites`
  - `follow-up check`
- The home-page final-readiness top next-action callout now renders the same
  release context, not just the immediate `release-start` handoff command.

## Verification

- `tests/test_final_plan.py::test_final_action_plan_release_next_action_keeps_commands_and_required_inputs`
- `tests/test_final_plan.py::test_render_final_next_action_shows_release_supporting_commands`
- `tests/test_final_readiness_web.py::test_render_final_readiness_panel_next_action_shows_release_commands`

## Boundary

This wave improves operator guidance only. It does not create Developer ID
credentials, a notary profile, a signed macOS artifact, or a signed Windows
installer.
