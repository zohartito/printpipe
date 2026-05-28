# Wave 132 - Release Final Readiness Handoff Commands

Status: complete for UI visibility. This is not signed distribution evidence.

## Problem

Release distribution actions already carried the real packaging/signing commands,
follow-up verification commands, required signing/tool inputs, and a generated
release handoff sheet. The home-page final-readiness rows only surfaced the
immediate `release-start` handoff command and handoff path, so the row did not
tell Zohar what credentials/tools were missing or what command comes next.

## Change

- Final-readiness action rows now preserve `required_inputs`.
- Rows preserve the action's actual `command` as a secondary run command when a
  separate `start_command` is the immediate handoff action.
- Rows preserve and render `followup_command`.
- The web checklist now renders release rows with:
  - Required inputs
  - Run after prerequisites
  - Follow-up check
  - Handoff

## Verification

- `tests/test_final_readiness_web.py::test_build_final_readiness_view_keeps_release_commands_and_required_inputs`
- `tests/test_final_readiness_web.py::test_render_final_readiness_panel_shows_release_commands_and_required_inputs`

## Boundary

This wave improves release execution visibility only. It does not create a
Developer ID certificate, notary profile, signed macOS artifact, or signed
Windows installer. The release distribution gate remains action-required until
those verified artifacts exist.
