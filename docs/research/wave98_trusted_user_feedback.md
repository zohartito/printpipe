# Wave 98 - Trusted-User Feedback Packets

Status: implemented.

## Problem

PrintPipe could record beta failures and physical evidence, but it did not have
a first-class packet for normal trusted-user feedback. That made successful or
partial beta runs less structured than failures.

## Decision

Add trusted-user feedback evidence:

```bash
printpipe record-beta-feedback runs/<run-id> \
  --tester "Maya" \
  --input-type existing_stl \
  --material "Bambu PLA Basic" \
  --printer "Bambu Lab P2S" \
  --outcome passed \
  --summary "Run completed and the report made sense." \
  --would-print no \
  --recommendation needs_review

printpipe beta-feedback-status --runs-dir runs --strict
```

Each packet writes:

- `90_beta/trusted_user_feedback.json`
- `90_beta/trusted_user_feedback.md`
- copied attachments under `90_beta/artifacts/`

## Gate

`build_beta_readiness_report()` now includes `trusted_user_beta`, which stays
action-required until at least three unique trusted users have recorded feedback
packets. `build_beta_action_plan()` uses the same status.

## Boundary

This plumbing does not invent beta evidence. It only records real feedback once
trusted users provide it.

## Verification

Verification passed:

```bash
.venv/bin/pytest tests/test_beta_feedback.py tests/test_beta_plan.py tests/test_beta_readiness.py
.venv/bin/pytest tests/test_beta_feedback.py tests/test_beta_plan.py tests/test_beta_readiness.py tests/test_cli_readiness.py tests/test_web_server.py tests/test_release_status.py
.venv/bin/python -m compileall -q src
git diff --check
.venv/bin/pytest
```

Results: focused beta packet tests passed, broader readiness/web/release checks
passed with 65 tests, compile and diff checks were clean, and the full suite
passed with 449 passed / 1 skipped.
