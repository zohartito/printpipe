# PrintPipe

Local-first reference-to-print pipeline.

PrintPipe is being built to turn an image, GIF, video, or existing mesh plus printer/filament intent into a verified Bambu-ready print package:

```text
input reference
-> cleaned frames
-> generated or imported mesh
-> repaired mesh
-> oriented/scaled bed-fit mesh
-> Bambu printer + filament profiles
-> Bambu-native .3mf
-> slice report
-> run receipt
```

## V1 Scope

- Local-first Mac/Windows program.
- Bambu printers only at launch.
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
| Image, GIF, video | Prepares references/contact sheets, then runs the configured Hunyuan3D local adapter through repair, orientation, Bambu 3MF bundling, and reports. If `PRINTPIPE_HUNYUAN3D_COMMAND` is not set, the run fails honestly at `meshgen` with provider-configuration receipts. |
| Prompt plus image | CLI supports `printpipe run image.png --prompt "..."`; the local web UI supports file plus prompt. The prompt is passed through to configured mesh providers as `prompt_hint`. |
| Prompt only | CLI supports `printpipe run --prompt "..."`; the local web UI supports prompt-only new runs. It writes `00_input/prompt.txt`, then uses the selected prompt-image provider to produce a reference image before the normal meshgen path. If no provider is configured, the run fails honestly at `prompt_reference_generation` with receipts. |

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

## Development

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest
printpipe --version
```
