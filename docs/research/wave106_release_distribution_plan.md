# Wave 106 Release Distribution Action Plan

Status: complete for release distribution planning. This is not signed release evidence.

## Finding

`printpipe release-status` correctly reported final distribution blockers, but the output was still mostly descriptive: install Developer ID identities, configure notarization, and build a signed Windows installer. The physical and trusted-user gates already had concrete action plans, so release distribution needed the same treatment.

## Change

- Added `printpipe.packaging.release_plan.build_release_distribution_plan()`.
- Added `printpipe release-plan --release-dir dist/release --runs-dir runs`.
- Added `/release-plan.json`.
- Added a home-page `Release distribution plan` panel.
- The plan emits concrete commands for:
  - rebuilding/verifying a release bundle when the manifest is invalid,
  - rebuilding the release with `--developer-id-identity` and `--notary-profile`,
  - building and including a signed Windows installer,
  - checking signing prerequisites with `printpipe doctor --json`.

## Current Local Result

With the current local machine state, the plan reports three action-required items:

- `macos_distribution`
- `windows_distribution`
- `signing`

## Boundary

This wave does not install certificates, configure Apple notarization, build a signed Windows installer, or mark the release as distributable. Only verified release manifest artifacts can close those gates.
