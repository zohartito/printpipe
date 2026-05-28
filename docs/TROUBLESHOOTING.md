# PrintPipe Troubleshooting

Status: foundation guide for the current local app and v1 packaging plan.

## Setup

Check the install first:

```bash
printpipe --version
printpipe doctor
```

If the command is not found, activate the virtual environment or reinstall the
editable package:

```bash
python -m pip install -e ".[dev]"
```

On Windows PowerShell, make sure the venv is active:

```powershell
.\.venv\Scripts\Activate.ps1
```

## Run Commands

Create a run folder:

```bash
printpipe init-run <input-file> --runs-dir runs
```

Run the current skeleton pipeline:

```bash
printpipe run <input-file> --runs-dir runs
```

Inspect a run:

```bash
printpipe status runs/<run-id>
printpipe open-report runs/<run-id>
printpipe open-folder runs/<run-id> --target bundle
printpipe open-folder runs/<run-id> --target report
```

If `printpipe run` reports that the Hunyuan3D local command is not configured,
set `PRINTPIPE_HUNYUAN3D_COMMAND` to the local adapter command before running
image/GIF/video inputs. Existing mesh inputs do not need that provider.

## `printpipe serve`

Start the local web UI:

```bash
printpipe serve --host 127.0.0.1 --port 8765 --runs-dir runs
```

If the page does not load, check that the command is still running and that the
same port is not already in use. Try another port:

```bash
printpipe serve --host 127.0.0.1 --port 9876 --runs-dir runs
```

Keep the default `127.0.0.1` host unless you intentionally want another device
on the local network to reach the server.

## Bambu Studio Paths

PrintPipe does not bundle Bambu Studio. Install Bambu Studio separately when a
slice gate or installed profile source is required.

Expected macOS locations:

```text
/Applications/BambuStudio.app
/Applications/BambuStudio.app/Contents/Resources/profiles/BBL/
~/Library/Application Support/BambuStudio/user/
```

Expected Windows candidates:

```text
C:\Program Files\Bambu Studio\
%APPDATA%\BambuStudio\user\
```

User presets should live below a numeric `user/<id>/` folder when present, or
below `user/default/` otherwise. Expected preset subfolders are `filament/`,
`process/`, and `machine/` on macOS, with the same names under Windows using
backslashes.

Do not write generated presets into the Bambu Studio application resources.

## Missing Dependencies

The base command should still work when optional components are missing. Use
these checks to narrow the issue:

- `printpipe --version`: verifies the CLI import path.
- `printpipe doctor`: checks Python, optional modules, Bambu Studio candidates,
  and Bambu profile user folders.
- `printpipe status runs/<run-id>`: verifies run/report discovery.
- `printpipe serve --host 127.0.0.1 --port 8765 --runs-dir runs`: verifies the
  local web server.

Known missing-dependency cases:

- Optional mesh repair requires `trimesh`; without it, repair should report that
  the feature is unavailable rather than failing at import time.
- Bambu Studio/Bambu CLI must be installed separately before a run can be called
  slice-verified.
- Missing Bambu profiles should report the profile name/type and searched roots.
- Missing run reports or artifacts should appear as `missing` in status and web
  surfaces.

## Packaging State

There is no finished v1 installer yet. Treat packaging docs as setup and smoke
test guidance while the macOS and Windows detector work lands.

The updater is later work and is not part of v1 packaging troubleshooting.
