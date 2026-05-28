# Wave 58 - Optional Standalone Release Artifact

## Question

Can the release handoff folder include the runtime-bundled macOS app while
keeping the default release path lightweight?

## Change

Added an opt-in standalone release path:

```bash
printpipe build-release \
  --output-dir dist/release \
  --adhoc-sign \
  --include-standalone \
  --pyinstaller "uvx --from pyinstaller pyinstaller" \
  --json
```

When enabled, the release folder includes:

- `PrintPipeStandalone-macOS.zip`

The manifest adds:

- `kind=macos_standalone_zip`
- `bundles_python_runtime=true`
- `bundles_bambu_studio=false`

The release boundary text switches from `No artifact bundles Python.` to
`macOS standalone artifact bundles Python; other artifacts do not.`

Live verification produced four manifest artifacts and `verify-release` returned
`ok` with 20 checks and 0 failures. After unzipping
`PrintPipeStandalone-macOS.zip`, the extracted app passed
`codesign --verify --deep --strict`, returned `printpipe 0.1.0`, and printed the
dry-run local web UI launcher.

## Boundary

This makes the runtime-bundled macOS app part of the release handoff only when
explicitly requested. It still does not solve Developer ID signing/notarization,
Windows signed installer work, Windows bundled runtime work, live Windows+Bambu
slicing, or physical print validation.
