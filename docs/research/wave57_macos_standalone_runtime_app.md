# Wave 57 - macOS Standalone Runtime App

## Question

Can PrintPipe build a macOS app that includes a Python runtime, instead of only
wrapping a zipapp that expects `/usr/bin/env python3`?

## Change

Added `printpipe build-macos-standalone`, backed by
`printpipe.packaging.macos_standalone.build_macos_standalone_app()`.

The command runs PyInstaller and then patches the generated app metadata so the
standalone app keeps the same local-app behavior:

- CLI passthrough for normal arguments
- no-argument local web UI launch
- one-file document launch into `printpipe run`
- alternate document types for supported mesh/media extensions
- explicit `bundles_python_runtime=true` reporting when PyInstaller includes a
  Python runtime

## Live Smoke

Command used:

```bash
.venv/bin/printpipe build-macos-standalone \
  --output /tmp/.../PrintPipeStandalone.app \
  --pyinstaller "uvx --from pyinstaller pyinstaller" \
  --json
```

Observed:

- `status=ok`
- `bundles_python_runtime=true`
- runtime path:
  `/tmp/.../PrintPipeStandalone.app/Contents/Resources/Python.framework`
- app size: about `75M`
- `Contents/MacOS/PrintPipeStandalone --version` returned `printpipe 0.1.0`
- `PRINTPIPE_APP_DRY_RUN=1 Contents/MacOS/PrintPipeStandalone` printed the
  local web UI launch command for `http://127.0.0.1:8765/`

## Boundary

This closes the macOS "bundled Python runtime exists" software gap, but not the
full distribution gap. The standalone app is still not Developer ID signed or
notarized, does not bundle Bambu Studio, is not yet the default release bundle
artifact, and does not register itself as the user's default file handler.
