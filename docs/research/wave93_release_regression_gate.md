# Wave 93 - Release Regression Gate

Status: complete.

## Why

Wave 92 made beta regression manifests visible in `printpipe readiness`, but
the stricter final handoff command, `printpipe release-status`, still called
readiness without a manifest. That meant a captured beta failure could be
replayed by readiness while the release gate stayed blind to the same drift.

## What Changed

- Added `regression_manifest_path` to `build_release_status_report()`.
- Passed the optional manifest through to `build_beta_readiness_report()`.
- Added `printpipe release-status --regression-manifest <manifest>`.
- Kept the existing injected `readiness_report` test seam intact for focused
  release-status tests.

## Boundary

This wave does not create real trusted-user beta failures, physical
PLA/PETG/TPU evidence, Apple Developer credentials, a notary profile, Windows
signing tools, or a Windows signing certificate. It only lets final release
status consume beta regression manifests when they exist.

## Verification

- Red check first: `tests/test_release_status.py` failed because the report
  builder and parser rejected `regression_manifest_path`.
- Green check: `tests/test_release_status.py` passed after implementation.
