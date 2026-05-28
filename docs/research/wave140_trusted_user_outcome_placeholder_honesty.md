# Wave 140 - Trusted-User Outcome Placeholder Honesty

Date: 2026-05-28

## Problem

Wave 139 made trusted-user feedback commands concrete, but the generated record command still included:

```bash
--outcome passed
--would-print no
--recommendation needs_review
```

That was too easy to copy into a false-positive feedback packet before a reviewer had actually made those calls.

## Change

Generated trusted-user feedback record commands now keep the concrete context:

- run root
- tester slot
- input type
- material
- printer
- report artifact path

But the reviewer judgment fields are explicit placeholders:

```bash
--outcome "<passed|failed|partial>"
--would-print "<yes|no|unknown>"
--recommendation "<recommendation>"
```

This keeps the command useful while making fake-positive evidence harder to create accidentally.

## Verification

Targeted red/green coverage:

```bash
.venv/bin/pytest \
  tests/test_beta_feedback.py::test_trusted_user_feedback_plan_lists_missing_tester_actions \
  tests/test_beta_feedback.py::test_beta_feedback_start_writes_handoff_without_satisfying_gate \
  tests/test_beta_feedback.py::test_trusted_user_feedback_plan_uses_concrete_handoff_commands \
  -q
```

Focused regression coverage:

```bash
.venv/bin/pytest tests/test_beta_feedback.py tests/test_final_plan.py tests/test_final_readiness_web.py tests/test_web_server.py -q
```

Local smoke:

```bash
.venv/bin/printpipe beta-feedback-plan --runs-dir runs --json
```

The current slipper trusted-user rows now require explicit reviewer outcome fields.

## Boundary

This is evidence-honesty hardening only. It does not create trusted-user feedback packets or close the beta gate.
