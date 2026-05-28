# Wave 43 - Portable Zipapp Package Artifact

Date: 2026-05-28

## Goal

Move packaging beyond smoke plans by producing a real distributable artifact that
can run without the editable-install console script.

## Artifact

Command:

```bash
printpipe build-zipapp --output dist/printpipe.pyz --json
```

The builder creates a stdlib Python zipapp with:

- source package copied from `src/printpipe`
- entrypoint `printpipe.cli:main`
- shebang `/usr/bin/env python3`
- no bundled Python runtime
- no bundled Bambu Studio

## Live Evidence

Command run:

```bash
OUTDIR=$(mktemp -d /tmp/printpipe-zipapp-live.XXXXXX)
.venv/bin/printpipe build-zipapp --output "$OUTDIR/printpipe.pyz" --json
python "$OUTDIR/printpipe.pyz" --version
python "$OUTDIR/printpipe.pyz" package-smoke --platform macos --runs-dir "$OUTDIR/runs" --json
```

Observed:

- zipapp artifact: `/tmp/printpipe-zipapp-live.s7Nm6f/printpipe.pyz`
- artifact size: `171814` bytes
- `python printpipe.pyz --version`: `printpipe 0.1.0`
- package smoke: `status=ok`
- generated run root:
  `/private/tmp/printpipe-zipapp-live.s7Nm6f/runs/20260528-063005-package-smoke-tiny-tetrahedron`
- bundle check: `ok`, with `existing_stl_package_smoke_tiny_tetrahedron.3mf`

## Boundary

This is a portable Python package artifact, not an OS-native installer.

Still open:

- signed/notarized macOS `.app`
- signed Windows installer
- bundled Python runtime
- Start Menu/Finder launcher integration
- file associations
- release-channel/update flow
