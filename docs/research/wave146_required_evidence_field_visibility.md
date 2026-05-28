# Wave 146 - Required Evidence Field Visibility

## Question

Do the final-plan and final-readiness surfaces show the evidence fields a human must fill before physical or trusted-user gates can close?

## Finding

Physical and trusted-user actions already carried `required_fields` in the JSON plans, but the human-facing renderers mostly showed commands, artifacts, and release `required_inputs`. When a row also had a detail message, the evidence fields were easy to miss.

That made the checklist less useful on print/review day: Zohar could see the record command, but not the required observations the packet needs.

## Change

- `final-plan` now preserves `required_fields` on the top `next_action` payload.
- Terminal `final-plan` and `final-next` render `required fields`.
- Web final-readiness rows preserve and render `Required evidence fields`.
- The web next-action callout can render `Next action required evidence fields`.

`required_fields` remain separate from release `required_inputs` so physical/beta observations are not confused with signing credentials or tool prerequisites.

## Verification

```bash
.venv/bin/pytest \
  tests/test_final_plan.py::test_final_action_plan_prefers_print_handoff_command_before_record_command \
  tests/test_final_plan.py::test_render_final_action_plan_lists_section_action_commands_and_files \
  tests/test_final_plan.py::test_render_final_next_action_shows_only_immediate_action \
  tests/test_final_readiness_web.py::test_build_final_readiness_view_flattens_section_actions \
  tests/test_final_readiness_web.py::test_render_final_readiness_panel_includes_honest_boundaries -q
```

Result: `5 passed`.

## Boundary

This is evidence-field visibility only. It does not fabricate physical or trusted-user proof. Gates still require real prints/reviews, real artifacts/photos where required, and explicit outcome packets.
