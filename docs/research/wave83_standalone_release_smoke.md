# Wave 83 - Standalone Runtime Release Smoke Evidence

## Command

```bash
printpipe build-release \
  --output-dir dist/release \
  --adhoc-sign \
  --include-standalone \
  --pyinstaller "uvx --from pyinstaller pyinstaller" \
  --json

printpipe verify-release dist/release --json
printpipe release-status --release-dir dist/release --runs-dir runs --json --strict
```

## Result

The ignored local `dist/release` folder now contains:

- `printpipe.pyz`
- `PrintPipe.dmg`
- `PrintPipe-Windows-portable.zip`
- `PrintPipeStandalone-macOS.zip`
- `release_manifest.json`

`verify-release` returned exit code `0` across 4 artifacts. The standalone ZIP
artifact verified as:

- kind: `macos_standalone_zip`
- path suffix: `.zip`
- `bundles_python_runtime=true`
- `bundles_bambu_studio=false`
- size and SHA-256 matched the manifest

`release-status --strict` returned exit code `2`, but the `release_bundle` gate
was `ready` with 4 verified artifacts. The remaining blockers were still:

- PLA/PETG/TPU physical evidence packets are missing.
- Developer ID Application and Developer ID Installer identities are not
  installed on this Mac.

## Boundary

This does not create a Developer ID signed/notarized macOS release. It proves
the local standalone-runtime release shape can be built and verified on this
machine.
