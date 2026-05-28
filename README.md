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
| Prompt plus image | Supported only at the provider-contract level as an optional `prompt_hint`; not wired through CLI/web runs yet. |
| Prompt only | Not supported yet. The pipeline needs an image/video/mesh source before it can produce geometry. |

Optional media cleanup hooks:

```bash
export PRINTPIPE_BACKGROUND_REMOVAL_COMMAND='your-bg-tool {input} {output}'
export PRINTPIPE_LIGHTING_NORMALIZATION_COMMAND='your-light-tool {input} {output}'
```

When unset, those stages stay as explicit no-op/copy receipts.

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

printpipe build-macos-app --output dist/PrintPipe.app
printpipe build-macos-app --output dist/PrintPipe.app --adhoc-sign
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
