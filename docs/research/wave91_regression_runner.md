# Wave 91 - Regression Manifest Runner

## Context

Wave 90 could capture beta failures and append manifest cases, but the manifest was still passive. Phase 16 needs a way to replay captured failures so expected failures, unexpected fixes, and regressions become visible.

## Change

- Added `printpipe.beta.regression.run_regression_manifest()`.
- Added `printpipe run-regressions <manifest>`.
- The runner executes each stored argv command and records:
  - expected outcome
  - actual outcome
  - exit code
  - stdout/stderr
  - pass/fail status
  - drift message
- `expected=failure` now passes only when the command exits nonzero.
- `expected=success` passes only when the command exits zero.
- `--strict` returns exit code `2` when any case drifts from expectation.

## Boundary

This does not create real beta failures or update material/orientation/repair rules by itself. It makes captured cases executable so those rule updates can be verified after they are made.

## Verification

```bash
.venv/bin/pytest tests/test_beta_regression.py
```
