# Wave 55 - Release Bundle Verifier

## Question

Can PrintPipe prove that a release handoff folder is still intact after it was
built?

## Change

Added `printpipe verify-release`, backed by
`printpipe.packaging.release.verify_release_bundle()`.

The verifier checks:

- `release_manifest.json` exists
- the manifest parses as JSON
- release boundary claims match current PrintPipe boundary text
- every artifact path stays inside the release folder
- every artifact exists
- every artifact size matches the manifest
- every artifact SHA-256 matches the manifest

The CLI exits `0` for intact folders and `2` when verification fails.

## Boundary

This proves release-folder integrity, not final distribution completeness. The
release can still be unnotarized, unsigned on Windows, runtime-dependent, and
missing physical print validation while passing integrity verification.
