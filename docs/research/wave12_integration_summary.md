# Wave 12 Integration Summary

Status: complete as software integration; physical print and real Bambu slice
gates remain separate evidence gates.

## What Landed

- Added oriented ASCII STL artifact writing with scale, Z rotation, XY centering,
  Z drop, and JSON sidecar receipts.
- Added optional `mesh-repair` extra with `trimesh`, plus a repair receipt helper
  that writes before/after stats and repaired-mesh artifacts.
- Upgraded contact sheets from JSON-only manifests to JSON plus local HTML
  previews.
- Added Bambu Studio CLI executable discovery and slice-command construction for
  macOS, Windows, Linux, env overrides, and extra candidates.
- Improved local web run cards with grouped artifact sections and direct `.3mf`
  download links when bundles exist.
- Documented remaining packaging, beta, and physical-print blockers.

## What Is Still Partial

- `printpipe run` still prepares inputs and reports; it does not yet drive the
  complete meshgen -> repair -> orient -> bundle -> slice chain in one command.
- Bambu Studio exists locally, but this wave did not launch the GUI/CLI slice
  gate because that should be a deliberate run against a chosen `.3mf`.
- Slipper, TPU, PLA, PETG, dogfood, and beta items still need physical evidence.

## Verification

```text
.venv/bin/python -m pip install -e '.[mesh-repair]'
.venv/bin/python -m pytest
243 passed, 1 skipped

git diff --check
passed
```
