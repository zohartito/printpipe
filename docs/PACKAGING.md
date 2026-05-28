# PrintPipe Packaging

Status: v1 packaging plan and operator notes. This is not a finished packaged
installer yet.

## V1 Goal

PrintPipe v1 should run locally on macOS and Windows, keep user data in local run
folders, and use the user's installed Bambu Studio/Bambu CLI for final slice
verification. Packaging should make setup predictable, but the core acceptance
gate remains the same as development: a run folder with receipts, a Bambu-native
`.3mf`, and a slice result when Bambu Studio is available.

The updater is explicitly later work, not v1.

## Current Developer Setup

Use the source checkout while packaging is still foundation work:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest
printpipe --version
```

On Windows PowerShell, activate the venv with:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
pytest
printpipe --version
```

## Running Locally

Current CLI commands are available from the editable install:

```bash
printpipe --version
printpipe init-run tests/fixtures/objects/existing_stl_pipeline/tiny_tetrahedron.stl --runs-dir runs
printpipe run tests/fixtures/objects/existing_stl_pipeline/tiny_tetrahedron.stl --runs-dir runs
printpipe status runs/<run-id>
printpipe open-report runs/<run-id>
printpipe doctor
```

`printpipe run` is still a skeleton pipeline for reports and prepared artifacts.
Do not describe the current foundation command as a finished print-ready
pipeline.

## Local Web UI

Start the stdlib local server with:

```bash
printpipe serve --host 127.0.0.1 --port 8765 --runs-dir runs
```

For local-only use, keep the default `127.0.0.1` host. Use `0.0.0.0` only when
intentionally exposing the server on the local network.

The current web UI is a foundation surface: it shows run status, report links,
artifact links, selectors, and a new-run form. It does not yet submit a full live
pipeline job.

## macOS Package Plan

V1 macOS packaging should provide a local launcher around the same `printpipe`
entry point, bundled with a compatible Python runtime and the required Python
dependencies. The package should not bundle Bambu Studio.

The package should detect:

- Bambu Studio app: `/Applications/BambuStudio.app`
- App-shipped profiles, read-only:
  `/Applications/BambuStudio.app/Contents/Resources/profiles/BBL/`
- User profile root:
  `~/Library/Application Support/BambuStudio/user/`

Generated or copied user presets should prefer a numeric
`user/<numeric_user_id>/` folder when present and fall back to `user/default/`.
Expected preset subdirectories are `filament/`, `process/`, and `machine/`.

Do not write into the Bambu Studio app bundle. Read from the app-shipped profile
tree or copy profile sources into PrintPipe run artifacts for receipts.

## Windows Package Plan

V1 Windows packaging should provide a local launcher around the same `printpipe`
entry point, bundled with a compatible Python runtime and the required Python
dependencies. The package should not bundle Bambu Studio.

The detector should check the common Bambu Studio install and user-data
locations first, then let the user provide explicit paths when detection fails:

- App install candidates such as:
  `C:\Program Files\Bambu Studio\`
- App-shipped profiles below the install resources tree, expected under a
  `profiles\BBL\` subtree.
- User profile root candidates such as:
  `%APPDATA%\BambuStudio\user\`

As on macOS, generated or copied user presets should prefer a numeric
`user\<numeric_user_id>\` folder when present and fall back to `user\default\`.
Expected preset subdirectories are `filament\`, `process\`, and `machine\`.

The exact Windows profile tree should be confirmed during the Windows packaging
smoke test before any installer writes presets automatically.

## Missing Dependency Handling

The base CLI should stay importable even when optional media, mesh repair, mesh
generation, or slicer integrations are unavailable. `printpipe --version`,
`printpipe status`, `printpipe open-report`, and `printpipe serve` should remain
useful for diagnosis.

Expected behavior for missing dependencies:

- Missing Python optional dependency: show the feature that is unavailable and
  the package or extra needed to enable it.
- Missing Bambu Studio/Bambu CLI: keep setup, report viewing, and non-slice
  checks available, but do not mark a run slice-verified.
- Missing Bambu profile source: show the searched roots and the requested
  printer, filament, or process profile.
- Missing run artifacts: report them as missing in status/report surfaces rather
  than crashing.

Use the doctor command for a single local check:

```bash
printpipe doctor
printpipe doctor --json
```

The report combines Python/runtime checks, optional dependency checks, Bambu
Studio install candidates, and Bambu Studio user profile folder candidates.

## Installer Smoke Checks

Before calling v1 packaging acceptable on either OS, run a clean-environment
smoke pass:

```bash
printpipe --version
printpipe serve --host 127.0.0.1 --port 8765 --runs-dir runs
printpipe init-run <existing-mesh.stl> --runs-dir runs
printpipe run <existing-mesh.stl> --runs-dir runs
printpipe status runs/<run-id>
printpipe doctor
```

When Bambu Studio is installed, add a Bambu path/profile detection check and a
slice-gate smoke check. When it is not installed, verify that the package reports
that limitation clearly.

## macOS Package Smoke Path

F10 is now backed by a non-interactive smoke command:

```bash
printpipe package-smoke --platform macos --runs-dir runs/package-smoke/macos --json
```

What this proves:

- The installed `printpipe` entry point starts.
- A generated ASCII STL fixture can be written without relying on repo test
  fixtures.
- The existing-mesh pipeline creates a run folder, reports, and a Bambu `.3mf`.
- `status` and `open-report` have real paths to inspect after the run.

What this does not prove:

- It is not a signed or notarized .app.
- It does not prove an installer drag/drop flow.
- It does not complete the live Bambu CLI slice gate. That check is recorded as
  `manual_required` in the smoke result while F13 owns the current Bambu Studio
  2.6.00.51 / macOS 26.5 CLI segfault.

## Windows Package Smoke Path

F11 has a matching Windows smoke command:

```powershell
printpipe package-smoke --platform windows --runs-dir runs/package-smoke/windows --json
```

On macOS or Linux, the command returns `manual_required` and tells the operator
to run this command on Windows. That is intentional: the pipeline code is
cross-platform, but a clean Windows packaging smoke pass needs the target
Windows shell, paths, permissions, and Bambu Studio install layout.

What the Windows command should prove when run on Windows:

- The installed `printpipe` entry point starts from PowerShell.
- A generated ASCII STL fixture can be written outside repo test fixtures.
- The existing-mesh pipeline creates a run folder, reports, and a Bambu `.3mf`.
- `status` and `open-report` resolve Windows paths cleanly.
- Missing Bambu Studio or optional dependencies are reported clearly rather
  than crashing.

What it does not prove yet:

- It is not a signed Windows installer.
- It has not been executed on a real Windows host from this Mac session.
- Live Bambu CLI slicing still needs a target-machine check after F13 or a
  Windows-specific workaround.

## Portable Zipapp Artifact

Wave 43 adds a concrete cross-platform Python artifact:

```bash
printpipe build-zipapp --output dist/printpipe.pyz --json
python dist/printpipe.pyz --version
python dist/printpipe.pyz package-smoke --platform macos --runs-dir runs/package-smoke/zipapp --json
```

What this proves:

- The source package can be bundled into one executable `.pyz` file with the
  `printpipe.cli:main` entrypoint.
- The artifact runs outside editable-install console scripts.
- The artifact can run the package-smoke pipeline and produce reports plus a
  Bambu `.3mf`.

What this does not prove:

- It does not bundle Python itself.
- It does not bundle Bambu Studio.
- It is not a signed/notarized macOS `.app`.
- It is not a signed Windows installer.
- It does not install shell shortcuts, file associations, or Start Menu/Finder
  launcher integration.

## Windows Zipapp Smoke Evidence

Wave 44 ran the same `printpipe.pyz` artifact on the Windows host over SSH:

```cmd
python %TEMP%\printpipe-zipapp\printpipe.pyz --version
python %TEMP%\printpipe-zipapp\printpipe.pyz package-smoke --platform windows --runs-dir %TEMP%\printpipe-zipapp\runs --json
```

Observed:

- `printpipe 0.1.0`
- `status=ok`
- Windows runtime check: `win32`
- generated fixture:
  `C:\Users\zohar_4ta16fp\AppData\Local\Temp\printpipe-zipapp\package_smoke_tiny_tetrahedron.stl`
- run root:
  `C:\Users\zohar_4ta16fp\AppData\Local\Temp\printpipe-zipapp\runs\20260528-063417-package-smoke-tiny-tetrahedron`
- bundle:
  `60_bundle\existing_stl_package_smoke_tiny_tetrahedron.3mf`

This upgrades the Windows packaging evidence from source-export smoke to actual
zipapp-artifact smoke. It still does not replace signed installer work.

## Windows Bambu CLI Boundary

Wave 45 checked `desktop-zt` for a callable Bambu Studio executable after the
zipapp smoke passed. No executable was found in the common Program Files or
LocalAppData locations, and a broader search for `BambuStudio.exe` returned no
matches.

Windows live slicing remains pending until Bambu Studio is installed on that
host or an explicit executable path is provided.

## Unsigned macOS App Bundle

Wave 46 adds an unsigned `.app` wrapper around the zipapp:

```bash
printpipe build-macos-app --output dist/PrintPipe.app --json
dist/PrintPipe.app/Contents/MacOS/printpipe --version
dist/PrintPipe.app/Contents/MacOS/printpipe package-smoke --platform macos --runs-dir runs/package-smoke/macos-app --json
```

What this proves:

- `PrintPipe.app` has a valid `Contents/Info.plist`.
- `Contents/MacOS/printpipe` is executable.
- `Contents/Resources/printpipe.pyz` is embedded.
- The app-bundle launcher runs the same CLI entrypoint as the source checkout.
- The launcher can run package-smoke and produce reports plus a Bambu `.3mf`.

What this does not prove:

- It is unsigned and not notarized.
- It uses `/usr/bin/env python3`; it does not bundle Python.
- It is a CLI launcher bundle, not a polished double-click GUI app.
- It does not bundle Bambu Studio.

## Ad-Hoc macOS App Signing

Wave 47 adds optional local ad-hoc signing:

```bash
printpipe build-macos-app --output dist/PrintPipe.app --adhoc-sign --json
codesign --verify --deep --strict dist/PrintPipe.app
```

Observed live:

- `signed=true`
- `signing_identity="-"`
- `notarized=false`
- `codesign --verify --deep --strict` returned `0`
- `Contents/MacOS/printpipe --version` returned `printpipe 0.1.0`

This is useful local packaging hygiene, but it is not Developer ID signing and
does not replace notarization.
