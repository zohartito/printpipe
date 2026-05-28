# Wave 92 - Regression Readiness Gate

Status: complete.

## Why

Wave 90 could capture beta failures and seed regression manifests. Wave 91
could replay those manifests. The gap was that readiness still ignored the
regression result, so a captured failure could drift without affecting the
same gate surfaces used for physical evidence, packaging, and release checks.

## What Changed

- Added an optional beta-regression gate to `build_beta_readiness_report()`.
- Added `printpipe readiness --regression-manifest <manifest>`.
- Kept a missing manifest non-blocking with `status=not_applicable`.
- Marked passing manifests `ready` with case counts.
- Marked drifted manifests `action_required` with an action pointing back to
  `printpipe run-regressions ... --strict`.

## Boundary

This wave does not create real trusted-user beta failures, physical print
evidence, or material/orientation/repair rule updates. It only makes captured
regression manifests visible in the readiness layer.

## Verification

- Red check first: focused readiness tests failed because the gate and CLI
  option did not exist.
- Green check: `tests/test_beta_readiness.py` and `tests/test_cli_readiness.py`
  passed after implementation.
