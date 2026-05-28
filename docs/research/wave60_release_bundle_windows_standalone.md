# Wave 60 - Release Bundle Windows Standalone Inclusion

## Question

Once the Windows standalone runtime ZIP has been built on a Windows host, can the
main release folder carry it as a checksummed artifact without pretending macOS
can cross-build it?

## Decision

Use an explicit prebuilt-artifact input:

```bash
printpipe build-release \
  --output-dir dist/release \
  --adhoc-sign \
  --windows-standalone-zip dist/PrintPipe-Windows-standalone.zip \
  --json
```

This keeps the build honest:

- macOS builds the generic handoff artifacts it can build locally.
- Windows builds the PyInstaller `.exe` ZIP on a Windows host.
- The release command copies and verifies that prebuilt Windows ZIP.

## Implementation

- Added `windows_standalone_zip` to `build_release_bundle()`.
- Added `--windows-standalone-zip` to `printpipe build-release`.
- The release builder copies the source ZIP to
  `PrintPipe-Windows-standalone.zip` inside the release folder.
- The builder verifies that the ZIP contains:
  - `PrintPipe/PrintPipe.exe`
  - bundled Python runtime files under `PrintPipe/_internal/`
- The manifest records the artifact as `windows_standalone_zip`.

## Manifest Claims

The copied artifact is recorded with:

- `bundles_python_runtime=true`
- `bundles_bambu_studio=false`
- `signed=false`
- `notarized=false`

The release boundary now distinguishes:

- macOS-only standalone runtime release
- Windows-only standalone runtime release
- combined macOS and Windows standalone runtime release

## Boundary

This is still not a signed Windows installer. It does not create Start Menu
entries, register file associations, or provide live Windows+Bambu Studio slice
evidence. Those remain separate gates.
