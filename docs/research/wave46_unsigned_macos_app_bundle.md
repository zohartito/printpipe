# Wave 46 - Unsigned macOS App Bundle

Date: 2026-05-28

## Goal

Turn the portable zipapp into a macOS `.app` bundle shape so packaging is more
than a command-line `.pyz` artifact.

## Artifact

Command:

```bash
printpipe build-macos-app --output dist/PrintPipe.app --json
```

The bundle contains:

- `Contents/Info.plist`
- `Contents/MacOS/printpipe`
- `Contents/Resources/printpipe.pyz`

The launcher script executes:

```bash
/usr/bin/env python3 Contents/Resources/printpipe.pyz "$@"
```

## Live Evidence

Command run:

```bash
OUTDIR=$(mktemp -d /tmp/printpipe-macos-app-live.XXXXXX)
.venv/bin/printpipe build-macos-app --output "$OUTDIR/PrintPipe.app" --json
"$OUTDIR/PrintPipe.app/Contents/MacOS/printpipe" --version
"$OUTDIR/PrintPipe.app/Contents/MacOS/printpipe" package-smoke --platform macos --runs-dir "$OUTDIR/runs" --json
```

Observed:

- app path: `/tmp/printpipe-macos-app-live.W27wn1/PrintPipe.app`
- executable:
  `/tmp/printpipe-macos-app-live.W27wn1/PrintPipe.app/Contents/MacOS/printpipe`
- embedded zipapp:
  `/tmp/printpipe-macos-app-live.W27wn1/PrintPipe.app/Contents/Resources/printpipe.pyz`
- `--version`: `printpipe 0.1.0`
- package smoke: `status=ok`
- generated bundle:
  `60_bundle/existing_stl_package_smoke_tiny_tetrahedron.3mf`

## Boundary

This is an unsigned CLI-launcher app bundle. It is not notarized, does not
bundle Python, does not bundle Bambu Studio, and is not yet a polished
double-click GUI application.
