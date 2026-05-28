# Wave 90 - Beta Failure Intake

## Context

Phase 16 still needs real beta users, failed runs, and rule updates. PrintPipe already had a beta failure data model and a regression manifest format, but there was no practical command for turning a failed run into durable evidence plus a regression case.

## Change

- Added `write_failure_report_files()` and `render_failure_report_markdown()` in `printpipe.beta.failures`.
- Added `printpipe record-beta-failure <run-root>`.
- Failure intake now writes:
  - `90_beta/failure_report.json`
  - `90_beta/failure_report.md`
  - copied artifacts under `90_beta/artifacts/`
- When `--regression-manifest` is provided, the command appends a `RegressionCase` seeded from the run manifest and the reproduction command.
- Updated the regression harness docs with the new CLI flow.

## Boundary

This does not invent failed beta evidence and does not complete Phase 16. It gives Zohar and trusted testers a repeatable way to capture failures after they happen, then turn them into regression fixtures instead of losing the context in chat screenshots or memory.

## Verification

```bash
.venv/bin/pytest tests/test_beta_failures.py
```
