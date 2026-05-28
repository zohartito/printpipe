# Wave 148 - Trusted-User Handoff Context Propagation

## Question

Do trusted-user beta review actions carry enough structured context for final-readiness surfaces to show what the review is about?

## Finding

Wave 147 made final-readiness capable of rendering evidence context when an action already had structured fields such as `run_root`, `tester`, `input_type`, `material`, and `printer`.

Trusted-user feedback handoff files already parsed that context from `trusted_user_feedback_handoff_*.md`, and the generated `record-beta-feedback` command included the same values. The action payload itself did not preserve those values as structured fields, so downstream consumers could only infer them by reading command text.

## Change

- Preserve trusted-user handoff context on each `beta-feedback-plan` review action.
- Include `run_root`, `tester`, `input_type`, `material`, and `printer`.
- Keep the existing generated review command and handoff/report/bundle artifact paths unchanged.
- Let `final-plan` and final-readiness inherit those fields through the existing Wave 147 context renderer.

## Verification

```bash
.venv/bin/pytest \
  tests/test_beta_feedback.py::test_trusted_user_feedback_plan_surfaces_handoff_report_and_bundle_paths \
  tests/test_beta_feedback.py::test_trusted_user_feedback_plan_uses_concrete_handoff_commands -q
```

Result: `2 passed`.

## Boundary

This is still handoff metadata only. It does not count as completed trusted-user feedback, does not close the beta gate, and does not replace review artifacts or returned tester packets.
