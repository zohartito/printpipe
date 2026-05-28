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
| Existing STL/OBJ/3MF mesh | Runs end-to-end through import, repair, orientation, Bambu 3MF bundling, reports, and optional slice gate. |
| Image, GIF, video | Prepares references/contact sheets, then runs the configured Hunyuan3D local adapter through repair, orientation, Bambu 3MF bundling, and reports. If `PRINTPIPE_HUNYUAN3D_COMMAND` is not set, the run fails honestly at `meshgen` with provider-configuration receipts. |
| Prompt plus image | Supported only at the provider-contract level as an optional `prompt_hint`; not wired through CLI/web runs yet. |
| Prompt only | Not supported yet. The pipeline needs an image/video/mesh source before it can produce geometry. |

## Development

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest
printpipe --version
```
