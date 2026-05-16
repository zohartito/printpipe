# PrintPipe

Local-first reference-to-print pipeline.

PrintPipe turns an image, GIF, video, or existing mesh plus printer/filament intent into a verified Bambu-ready print package:

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

Foundation repo. The 142-item execution map lives in:

- [docs/APP_ROADMAP.md](docs/APP_ROADMAP.md)
- [docs/AGENT_WAVES.md](docs/AGENT_WAVES.md)

## Development

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest
printpipe --version
```

