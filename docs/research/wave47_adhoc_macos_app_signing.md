# Wave 47 - Ad-Hoc macOS App Signing

Date: 2026-05-28

## Goal

Improve the macOS app bundle from unsigned to locally verifiable with ad-hoc
codesign, without claiming Developer ID signing or notarization.

## Command

```bash
OUTDIR=$(mktemp -d /tmp/printpipe-macos-app-signed.XXXXXX)
.venv/bin/printpipe build-macos-app --output "$OUTDIR/PrintPipe.app" --adhoc-sign --json
codesign --verify --deep --strict "$OUTDIR/PrintPipe.app"
"$OUTDIR/PrintPipe.app/Contents/MacOS/printpipe" --version
```

## Result

- app path: `/tmp/printpipe-macos-app-signed.8YBifV/PrintPipe.app`
- `signed`: `true`
- `signing_identity`: `-`
- `notarized`: `false`
- `codesign --verify --deep --strict`: return code `0`
- launcher version: `printpipe 0.1.0`

## Boundary

Ad-hoc signing is useful local packaging hygiene only. It does not prove
Developer ID signing, notarization, bundled Python runtime, or Gatekeeper-ready
distribution.
