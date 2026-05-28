# Wave 99 - Trusted Feedback Status in Local Web UI

Status: implemented.

## Problem

Wave 98 added structured trusted-user feedback packets and CLI/readiness gates,
but the local browser app did not have a direct trusted feedback status endpoint
or home-page panel. The beta action plan mentioned trusted-user beta, but the
packet count and tester names were not visible as their own evidence surface.

## Decision

Add a read-only web surface for the same status produced by
`build_trusted_user_feedback_status()`:

- `GET /beta-feedback-status.json`
- home-page `Trusted-user feedback` panel
- service link to the JSON endpoint

The panel shows overall status, unique trusted-user count, missing count, packet
count, tester names, and outcome counts. It keeps the proof boundary explicit:
trusted-user feedback is not physical print proof.

## Verification

Verification passed:

```bash
.venv/bin/pytest tests/test_web_server.py -k "beta_feedback_status or trusted_user_feedback_gate or launch_controls"
.venv/bin/pytest tests/test_web_server.py tests/test_beta_feedback.py tests/test_beta_plan.py tests/test_beta_readiness.py
.venv/bin/python -m compileall -q src
git diff --check
.venv/bin/pytest
```

Results: focused red/green web tests passed, the focused web/beta pack passed
with 56 tests, compile and diff checks were clean, and the full suite passed
with 451 passed / 1 skipped.
