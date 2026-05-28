# Wave 147 - Evidence Context Visibility

## Question

Do the final-plan and final-readiness handoffs show what the remaining evidence is about, not just the command and required fields?

## Finding

Physical-validation actions already carried useful context such as:

- `material_hint`
- `object_label`
- `print_type`
- `run_root`

Those fields were visible in the raw action JSON, but the top next-action payload and web checklist rows did not preserve or render them. That meant the operator could see the command to run, but not a compact summary of which material, object, print type, or run folder the evidence belonged to.

## Change

- Preserve context fields on `final-plan` top next actions.
- Render terminal `evidence context` lines in `final-plan` and `final-next`.
- Preserve the same fields in web final-readiness action rows.
- Render web `Evidence context` lines in checklist rows.
- Support material hint, material, printer, object label, print type, input type, tester, and run folder.

## Verification

```bash
.venv/bin/pytest \
  tests/test_final_plan.py::test_final_action_plan_prefers_print_handoff_command_before_record_command \
  tests/test_final_plan.py::test_render_final_next_action_shows_only_immediate_action \
  tests/test_final_readiness_web.py::test_build_final_readiness_view_flattens_section_actions \
  tests/test_final_readiness_web.py::test_render_final_readiness_panel_includes_honest_boundaries -q
```

Result: `4 passed`.

## Boundary

Evidence context is still only handoff metadata. It does not satisfy physical validation, trusted-user beta, or release distribution gates.
