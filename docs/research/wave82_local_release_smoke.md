# Wave 82 - Local Release Bundle Smoke Evidence

## Commands

```bash
printpipe build-release --output-dir dist/release --adhoc-sign --json
printpipe verify-release dist/release --json
printpipe release-status --release-dir dist/release --runs-dir runs --json --strict
```

## Result

`build-release` produced an ignored local release folder at `dist/release` with:

- `printpipe.pyz`
- `PrintPipe.dmg`
- `PrintPipe-Windows-portable.zip`
- `release_manifest.json`

`verify-release` returned exit code `0`. It verified:

- manifest presence and JSON syntax
- current boundary claims
- artifact path containment
- type-specific artifact metadata
- artifact existence
- artifact byte sizes
- artifact SHA-256 hashes

`release-status --strict` returned exit code `2`, but the release bundle gate
was `ready`. The remaining action-required gates were:

- PLA/PETG/TPU physical evidence packets are missing.
- Developer ID Application and Developer ID Installer identities are not
  installed on this Mac.

## Boundary

This is local smoke evidence only. `dist/` is intentionally ignored, so the
binary artifacts are not committed. This does not produce a Developer ID
signed/notarized macOS release, a signed Windows installer, or physical print
validation.
