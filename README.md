# PrintPipe

Local-first reference-to-print pipeline.

Today it takes an existing mesh (STL/OBJ/3MF) to a repaired, oriented, Bambu-ready `.3mf` with a slice report; image, GIF, video and prompt inputs are in progress and need a configured mesh-generation provider.

Install and run (Python 3.11+):

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[mesh-repair]"
printpipe run path/to/model.stl --runs-dir runs
```

Slicing (`--slice`) also needs a local Bambu Studio install, found automatically or set with `PRINTPIPE_BAMBU_STUDIO_CLI`; without it the slice step is skipped and reported as such.

PrintPipe is being built to turn an image, GIF, video, or existing mesh plus printer/filament intent into a verified Bambu-ready print package:

```text
input reference
-> cleaned frames
-> generated or imported mesh
-> repaired mesh
-> oriented/scaled bed-fit mesh
-> P2S printer profile + material-specific filament settings
-> Bambu-native .3mf
-> slice report
-> run receipt
```

## V1 Scope

- Local-first Mac/Windows program.
- Current bundles target Bambu Lab P2S with a 0.4 mm nozzle and a 256 x 256 x 256 mm envelope.
- `--printer` is a report/checklist label; it does not select a machine profile or bed size. Other printer labels still export P2S settings.
- Single-material prints only.
- Mesh generation is provider-based: hosted GPU, local model, API provider, or imported mesh.
- Every run produces receipts: artifacts, logs, settings delta, and slicer outcome.

The slipper project is the proof of concept, not the product boundary.

## Current Status

Foundation repo. The current end-to-end spine is existing mesh input. The 142-item execution map lives in:

- [docs/APP_ROADMAP.md](docs/APP_ROADMAP.md)
- [docs/AGENT_WAVES.md](docs/AGENT_WAVES.md)

Current input support is intentionally explicit:

| Input mode | Current behavior |
| --- | --- |
| Existing STL/OBJ/3MF mesh | Runs end-to-end through import, repair, orientation, Bambu 3MF bundling, reports, and optional Bambu CLI slice gate. |
| Image, GIF, video | Prepares references/contact sheets, then runs a configured media meshgen adapter through repair, orientation, Bambu 3MF bundling, and reports. `PRINTPIPE_MEDIA_MESHGEN_COMMAND` is the generic command hook; `PRINTPIPE_HUNYUAN3D_COMMAND` remains the Hunyuan-specific hook. If neither is set, the run fails honestly at `meshgen` with provider-configuration receipts. |
| Prompt plus image | CLI supports `printpipe run image.png --prompt "..."`; the prompt is passed through to configured mesh providers as `prompt_hint`. |
| Prompt only | CLI supports `printpipe run --prompt "..."`. It writes `00_input/prompt.txt`, then uses the selected prompt-image provider to produce a reference image before the normal meshgen path. If no provider is configured, the run fails honestly at `prompt_reference_generation` with receipts. |

`printpipe doctor` and `printpipe readiness` also surface media-meshgen readiness
upfront, so image/GIF/video/prompt runs show an action-required setup gate when
no live provider is configured. A configured provider only satisfies the
release/beta readiness gate after a successful `media-meshgen-smoke` receipt is
present under the runs directory. This is an output-file/receipt existence check:
it does not validate mesh geometry, hash the output, or bind old receipts to the
current command and parameters. Even an empty output can pass. After changing a
provider or its parameters, rerun the smoke and inspect the resulting mesh;
`--strict` and readiness alone do not prove the current provider works.

Generate a starter script for the generic media meshgen hook:

```bash
printpipe media-meshgen-template --output scripts/media_meshgen_adapter.py
export PRINTPIPE_MEDIA_MESHGEN_COMMAND="$(pwd)/scripts/media_meshgen_adapter.py"
printpipe media-meshgen-smoke reference.png --runs-dir runs/media-meshgen-smoke
printpipe media-meshgen-smoke-status --runs-dir runs --strict
```

For a no-dependency plumbing smoke, PrintPipe also ships a local heightfield
adapter. It turns a PNG reference into a printable relief STL and proves the
adapter protocol, but it is not semantic AI object reconstruction:

```bash
printpipe media-meshgen-smoke reference.png \
  --command "printpipe media-meshgen-heightfield" \
  --runs-dir runs/media-meshgen-smoke
```

One-off smoke receipts record the command invoked and its reported output path.
If that command is not yet configured in the environment, `printpipe final-next`
will surface the exact local config handoff instead of sending you back to the
blank adapter template:

```bash
printpipe media-meshgen-configure --command "printpipe media-meshgen-heightfield"
```

That writes `.printpipe/config.json`, which is intentionally ignored by git.
The saved command is inactive until you review it and explicitly trust it:

```bash
export PRINTPIPE_CONFIG_PATH="$(pwd)/.printpipe/config.json"
printpipe media-meshgen-smoke reference.png --runs-dir runs/media-meshgen-smoke
```

Alternatively, set `PRINTPIPE_TRUST_PROJECT_MEDIA_COMMAND=1` in the reviewed
workspace. Configuration alone does not enable provider execution.
For a ComfyUI API workflow, persist the workflow and patch paths beside the
command:

```bash
printpipe media-meshgen-template --preset comfyui-api --output scripts/media_meshgen_adapter.py
printpipe media-meshgen-comfyui-inspect workflows/image_to_glb.json
printpipe media-meshgen-configure \
  --command "python scripts/media_meshgen_adapter.py" \
  --params-json '{"comfyui_workflow":"workflows/image_to_glb.json","comfyui_image_paths":["12.inputs.image"]}'
```

The local web app is read-only: it exposes status and local artifact links, but
web run creation, provider configuration, workflow uploads, smoke execution,
and re-slicing are disabled. Use the CLI commands above to configure a trusted
local workflow. Doctor/readiness checks re-inspect that saved workflow later, so
deleted or edited workflow JSON does not keep counting as a live media provider.
Before running a full smoke, check whether the ComfyUI API is reachable and has
the expected 3D node class:

```bash
printpipe media-meshgen-comfyui-preflight --json --strict
```

CLI smoke tests resolve the adapter command and adapter params from the same
project workspace when a workspace is provided.
Successful smoke receipts preserve safe adapter params, so a tested ComfyUI
workflow can be promoted into project config without losing workflow or patch
paths. The ComfyUI runtime preflight and CLI setup steps still do not prove
semantic reconstruction; a real `media-meshgen-smoke` receipt is required before
the media gate is ready.
`printpipe final-plan` and `printpipe final-next` include this provider/smoke
gate before physical beta/release handoffs when it is still missing.

Optional media cleanup hooks:

```bash
export PRINTPIPE_BACKGROUND_REMOVAL_COMMAND='your-bg-tool {input} {output}'
export PRINTPIPE_LIGHTING_NORMALIZATION_COMMAND='your-light-tool {input} {output}'
export PRINTPIPE_PROMPT_IMAGE_COMMAND='your-image-tool --prompt-file {prompt_file} --output {output}'
```

When unset, those stages stay as explicit no-op/copy receipts.

Prompt-only runs can use either a configured command or the OpenAI Images API:

```bash
# Existing local/custom hook.
printpipe run --prompt "small ergonomic desk hook" \
  --prompt-image-provider command

# Built-in OpenAI prompt-image adapter.
export OPENAI_API_KEY='sk-...'
printpipe run --prompt "small ergonomic desk hook" \
  --prompt-image-provider openai
```

OpenAI prompt-image defaults are conservative and configurable:

```bash
export PRINTPIPE_OPENAI_IMAGE_MODEL='gpt-image-2'
export PRINTPIPE_OPENAI_IMAGE_SIZE='1024x1024'
export PRINTPIPE_OPENAI_IMAGE_QUALITY='low'
export PRINTPIPE_OPENAI_IMAGE_ESTIMATED_COST_USD='0.012'
export PRINTPIPE_PROMPT_IMAGE_MAX_COST_USD='0.05'
```

When a max cost is set, OpenAI prompt-image runs fail before the API call if the
estimate is missing or above the cap. The estimate is user-configured because
provider pricing can drift.

Flexible-material runs, including TPU, also emit `40_geometry/flex_coupon_40x15x3.stl` as the first validation print artifact.

Example material slice runs:

```bash
printpipe run input.stl \
  --runs-dir runs \
  --material "SUNLU TPU 90A" \
  --printer "Bambu Lab P2S" \
  --use-case "wearable slipper" \
  --slice

printpipe run input.stl --runs-dir runs --material "PLA" --slice
printpipe run input.stl --runs-dir runs --material "PETG" --slice
printpipe run --prompt "small ergonomic desk hook" --runs-dir runs
```

Process overrides (`--set`, with `--slice`) are applied without final enum/schema
validation. Unknown keys may be warned about but are still applied; bundle
validation does not certify setting values. Review overrides and slicer results.

PETG bundles select Textured PEI in project settings so Bambu Studio does not treat them as Cool Plate jobs.
Current software material coverage includes PLA/PLA+, PETG, TPU, ABS, ASA, PC, PA, and PA-CF bundle settings with Bambu CLI slice receipts.

Local handoff helpers:

```bash
printpipe open-folder runs/<run-id> --target bundle
printpipe open-folder runs/<run-id> --target report
```

Portable Python package artifact:

```bash
printpipe build-zipapp --output dist/printpipe.pyz
python dist/printpipe.pyz --version
python dist/printpipe.pyz package-smoke --platform macos --runs-dir runs/package-smoke/zipapp --json
printpipe build-windows-portable --output dist/PrintPipe-Windows-portable.zip
printpipe build-windows-standalone --output dist/PrintPipe-Windows-standalone.zip --pyinstaller "pyinstaller"
printpipe build-windows-installer --standalone-zip dist/PrintPipe-Windows-standalone.zip --output dist/PrintPipeSetup.exe --certificate-subject "CN=Your Code Signing Certificate"

printpipe build-release --output-dir dist/release --adhoc-sign
printpipe build-release --output-dir dist/release --adhoc-sign --include-standalone --pyinstaller "uvx --from pyinstaller pyinstaller"
printpipe build-release --output-dir dist/release --adhoc-sign --windows-standalone-zip dist/PrintPipe-Windows-standalone.zip
printpipe build-release --output-dir dist/release --windows-installer-exe dist/PrintPipeSetup.exe
printpipe build-release --output-dir dist/release --developer-id-identity "Developer ID Application: Your Name (TEAMID)" --notary-profile printpipe-notary
printpipe verify-release dist/release --json

printpipe build-macos-app --output dist/PrintPipe.app
printpipe build-macos-app --output dist/PrintPipe.app --adhoc-sign
printpipe build-macos-app --output dist/PrintPipe.app --developer-id-identity "Developer ID Application: Your Name (TEAMID)"
printpipe build-macos-standalone --output dist/PrintPipeStandalone.app --pyinstaller "uvx --from pyinstaller pyinstaller"
printpipe build-macos-dmg --output dist/PrintPipe.dmg --adhoc-sign
printpipe build-macos-dmg --output dist/PrintPipe.dmg --developer-id-identity "Developer ID Application: Your Name (TEAMID)" --notary-profile printpipe-notary
PRINTPIPE_APP_DRY_RUN=1 dist/PrintPipe.app/Contents/MacOS/printpipe
PRINTPIPE_APP_DRY_RUN=1 dist/PrintPipeStandalone.app/Contents/MacOS/PrintPipeStandalone
PRINTPIPE_APP_DRY_RUN=1 dist/PrintPipe.app/Contents/MacOS/printpipe path/to/input.stl
dist/PrintPipe.app/Contents/MacOS/printpipe --version
```

`--windows-installer-exe` copies a prebuilt installer into the release folder,
but it does not by itself prove Authenticode signing. `verify-release` requires
real signature verification before a Windows installer can close the signed
distribution gate.

For a restricted MCP server, set `PRINTPIPE_MCP_INPUT_ROOT` and
`PRINTPIPE_MCP_OUTPUT_ROOT` before startup. The supplied registration confines
inputs to the working checkout and outputs to its `runs/` folder. Paths are
resolved and symlinks below those roots are rejected; tool arguments cannot
change the policy. Manual module startup without these variables retains
unrestricted local path access.

## Development

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,mesh-repair]"
pytest
printpipe --version
```

## License

AGPL-3.0-or-later. See [LICENSE](LICENSE).
