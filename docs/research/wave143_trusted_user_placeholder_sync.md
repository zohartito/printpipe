# Wave 143 - Trusted-User Handoff and Fallback Placeholder Sync

## Question

After Wave 140 fixed concrete trusted-user feedback commands, were there still stale places where PrintPipe suggested a passing review outcome before a real tester responded?

## Finding

Yes. The current `beta-feedback-plan` concrete commands were safe, but three stale surfaces still preselected values:

- `src/printpipe/beta/beta_plan.py` fallback command used `--outcome passed`, `--would-print no`, and `--recommendation needs_review`.
- `docs/beta/onboarding.md` showed the same preselected values.
- Existing local slipper handoff sheets under `runs/20260528-042826-slipper-size11-v2c-wide-upper-textured/90_beta/` still carried the old command text.

Those values are valid results in some cases, but they should come from a real trusted-user review, not from a generated template.

## Change

The fallback and docs now require:

```bash
--outcome "<passed|failed|partial>"
--would-print "<yes|no|unknown>"
--recommendation "<recommendation>"
```

The existing local trusted-user handoff Markdown sheets were refreshed to use the same placeholders while preserving the concrete run folder, tester slot, material, printer, report artifact, and bundle context.

## Tests

Added/updated guardrails in:

- `tests/test_beta_plan.py`
- `tests/test_beta_onboarding_docs.py`

Targeted verification:

```bash
.venv/bin/pytest tests/test_beta_plan.py::test_beta_action_plan_reports_missing_beta_evidence tests/test_beta_onboarding_docs.py::test_onboarding_doc_does_not_preselect_trusted_feedback_outcome tests/test_beta_feedback.py::test_beta_feedback_start_writes_handoff_without_satisfying_gate tests/test_beta_feedback.py::test_trusted_user_feedback_plan_uses_concrete_handoff_commands -q
```

Result:

```text
4 passed
```

## Boundary

This removes stale fake-positive command defaults. It still does not create trusted-user evidence. The beta gate remains open until three unique trusted users return completed feedback packets with supporting evidence.
