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
python -m pip install -e ".[dev,mesh-repair]"
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

If `printpipe run` reports that no media meshgen command is configured, set
`PRINTPIPE_MEDIA_MESHGEN_COMMAND` to any adapter that accepts PrintPipe's
`--source`, `--output`, `--output-format`, and related arguments. The older
Hunyuan-specific hook still works via `PRINTPIPE_HUNYUAN3D_COMMAND`. Existing
mesh inputs do not need either provider.
`printpipe doctor` and `printpipe readiness --strict` show the same provider
gap before you start a media run.

To scaffold a concrete ComfyUI API adapter handoff instead of starting from a blank file:

```bash
printpipe media-meshgen-template --preset comfyui-api --output scripts/media_meshgen_adapter.py
printpipe media-meshgen-comfyui-inspect workflows/image_to_glb.json
printpipe media-meshgen-configure \
  --command "python scripts/media_meshgen_adapter.py" \
  --params-json '{"comfyui_url":"http://127.0.0.1:8188","comfyui_workflow":"workflows/image_to_glb.json","comfyui_image_paths":["12.inputs.image"]}'
printpipe media-meshgen-smoke reference.png --runs-dir runs/media-meshgen-smoke --output-format glb
printpipe media-meshgen-smoke-status --runs-dir runs --strict
```

The generated script is executable and intentionally exits with an adapter
setup error until the saved `comfyui_workflow` path points at a real exported
ComfyUI API workflow ending in `SaveGLB`, with prompt/image patch paths supplied
as needed. Environment variables like `PRINTPIPE_COMFYUI_WORKFLOW` still override
saved params. Use `--preset generic` if you want the blank adapter protocol stub.
`media-meshgen-comfyui-inspect` reads exported workflow JSON and suggests the
`comfyui_image_paths`, `comfyui_prompt_paths`, and `comfyui_seed_paths` to store.
The browser is read-only: workflow uploads, provider configuration, and smoke
execution are disabled. Use `media-meshgen-configure --params-json ...` and the
other CLI commands above. Doctor/readiness re-run static workflow validation, so
deleting or editing the saved workflow can move the provider back to
action-required before smoke/run time. These CLI setup paths do not contact
ComfyUI or close readiness without a successful smoke receipt.
When a one-off smoke succeeds, `media-meshgen-smoke-status` can preserve safe
adapter params so the follow-up configure command does not drop ComfyUI workflow
or patch paths.
For adapter-protocol plumbing only, use the built-in PNG heightfield adapter:

```bash
printpipe media-meshgen-smoke reference.png \
  --command "printpipe media-meshgen-heightfield" \
  --runs-dir runs/media-meshgen-smoke
```

That command writes a real STL relief mesh from the PNG pixels, but it is not a
semantic image-to-object model.
Successful one-off smoke receipts record the command that produced the mesh, so
`printpipe final-next` can point at the exact local config step when the command
is proven but not configured in the current environment:

```bash
printpipe media-meshgen-configure --command "printpipe media-meshgen-heightfield"
```

The command writes `.printpipe/config.json`, which is local-machine state and is
ignored by git.
For ComfyUI adapters, use runtime preflight before a full smoke when the workflow
looks right but the provider still fails:

```bash
printpipe media-meshgen-comfyui-preflight --json --strict
```

That checks the ComfyUI API URL for `/system_stats`, `/object_info`, and the
required node class `SaveGLB`. It only proves reachability and node availability;
it does not queue the workflow or replace the smoke receipt.
`media-meshgen-smoke` creates a narrow run folder and writes
`20_meshgen/smoke.json`, `summary.json`, and `attempts.jsonl` without repairing,
bundling, or slicing. Use it to prove the adapter writes a mesh before starting a
full PrintPipe run. `printpipe readiness --strict` treats a configured provider
without a successful smoke receipt as action-required instead of ready.
Use `media-meshgen-smoke-status` to inspect the smoke receipts directly before
debugging broader readiness gates. The local web app mirrors this status on the
home page and at `/media-meshgen-smoke-status.json`. `final-plan` and
`final-next` also surface this gate before physical, beta, and release handoffs
when provider proof is still missing.

If an OBJ, GLB, GLTF, or 3MF input fails at `mesh_repair` with a
`printpipe[mesh-repair]` message, install the optional mesh repair dependencies
or convert the model to ASCII STL before importing it.

If `record-physical-evidence` says `photo/artifact file not found`, replace the
placeholder `--photo /path/to/...` or `--artifact ...|/path/to/file|...` value
with a real file path from the machine running the command.

## macOS Desktop and Privacy Permissions

macOS privacy/TCC can block Terminal, Codex, Cursor, VS Code, or another shell
from reading files in protected folders such as Desktop, Documents, Downloads,
external drives, or synced cloud folders. This is different from normal Unix
file permissions, so `chmod` is usually the wrong first fix.

Common symptoms:

- `printpipe doctor` shows a filesystem warning for the workspace or an
  external artifact path.
- `printpipe status` or the local web UI marks an artifact as `unreadable`.
- A path exists in Finder, but Python, git, or PrintPipe cannot read it.

Recovery path:

1. Prefer moving the checkout and run folders to an unprotected workspace such
   as `~/Projects/printpipe` or `~/Code/printpipe`.
2. If the project must stay on Desktop or another protected location, open
   System Settings -> Privacy & Security -> Full Disk Access and grant access
   to every app that launches PrintPipe: Terminal, iTerm, Codex, Cursor, VS
   Code, or the packaged PrintPipe app.
3. Quit and reopen the granted app. macOS usually applies TCC grants only after
   the process restarts.
4. Re-run `printpipe doctor`.
5. For external artifacts, run doctor with explicit artifact paths:

```bash
PRINTPIPE_ARTIFACT_PATHS="/path/to/model.stl:/path/to/other/folder" printpipe doctor
```

If only one referenced artifact is unreadable, copy that file into the run
folder or another readable folder and rebuild the run. If the primary checkout
is unreadable, fix that first before debugging meshgen, slicing, or the web UI.

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

`127.0.0.1` is the only supported web bind address. PrintPipe rejects LAN,
hostname, and IPv6 bind addresses because the browser UI has no user
authentication or per-run authorization.

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
  Bambu profile user folders, workspace readability, and configured external
  artifact readability.
- `printpipe status runs/<run-id>`: verifies run/report discovery.
- `printpipe serve --host 127.0.0.1 --port 8765 --runs-dir runs`: verifies the
  local web server.

Known missing-dependency cases:

- Optional mesh repair requires `trimesh`. Open-mesh hole filling also requires
  `networkx`; without it, repair should report the missing dependency instead
  of failing with a traceback.
- Bambu Studio/Bambu CLI must be installed separately before a run can be called
  slice-verified.
- Missing Bambu profiles should report the profile name/type and searched roots.
- Missing run reports or artifacts should appear as `missing` in status and web
  surfaces.
- Unreadable external artifacts should appear as `unreadable` in status/web
  surfaces instead of crashing the page.

To make `printpipe doctor` check specific external artifact folders or files,
set `PRINTPIPE_ARTIFACT_PATHS` with paths separated by the OS path separator
(`:` on macOS/Linux, `;` on Windows) before running doctor.

## Packaging State

There is no finished v1 installer yet. Treat packaging docs as setup and smoke
test guidance while the macOS and Windows detector work lands.

The updater is later work and is not part of v1 packaging troubleshooting.
