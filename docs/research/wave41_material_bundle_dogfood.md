# Wave 41 - PLA/PETG Material Bundle Dogfood

Date: 2026-05-28

## Goal

Move PLA and PETG from "rules exist" to "rules are present in generated Bambu
bundles and survive a real Bambu CLI slice."

## Findings

- PLA/PETG material rule modules existed, but the pipeline bundle config only
  had a real override path for TPU.
- Non-TPU materials fell through to the Generic PLA bundle baseline, so PETG
  could be selected by name without actually changing generated project
  settings.
- Live PETG slicing initially failed with:
  `Plate 1: Cool Plate does not support filament 1`.
- Adding `curr_bed_type=Textured PEI Plate` to PETG project settings fixed the
  Bambu validation failure.

## Changes

- PLA and PLA+ material overrides now merge into generated 3MF project settings.
- PETG material overrides now merge into generated 3MF project settings.
- PETG now carries `curr_bed_type=Textured PEI Plate` as a material bed-adhesion
  rule.
- Bundle regression tests now use intentionally wrong fake profile defaults so
  they fail if material rules are not actually applied.

## Live Slice Evidence

Host:

- Bambu Studio: `/Applications/BambuStudio.app/Contents/MacOS/BambuStudio`
- Version observed in prior slice work: `02.06.00.51`
- macOS: `26.5`

Commands:

```bash
.venv/bin/printpipe run tests/fixtures/objects/existing_stl_pipeline/tiny_tetrahedron.stl \
  --runs-dir /tmp/printpipe-material-slice-pla.ASW7w2 \
  --material "PLA" \
  --slice \
  --bambu-cli /Applications/BambuStudio.app/Contents/MacOS/BambuStudio

.venv/bin/printpipe run tests/fixtures/objects/existing_stl_pipeline/tiny_tetrahedron.stl \
  --runs-dir /tmp/printpipe-material-slice-petg-fixed.lxxrRb \
  --material "PETG" \
  --slice \
  --bambu-cli /Applications/BambuStudio.app/Contents/MacOS/BambuStudio
```

Results:

| Material | Return | Warnings | Errors | Time | Filament | Layers |
| --- | ---: | --- | --- | ---: | ---: | ---: |
| PLA | 0 | `[]` | `[]` | 139 s | 0.28 g | 47 |
| PETG | 0 | `[]` | `[]` | 141 s | 0.28 g | 47 |

## Boundary

This completes the software/slice side of original material test items 109-111.
It does not complete F9 physical validation: real PLA, PETG, and TPU coupon or
small-object prints still need photos/notes recorded through
`printpipe record-physical-evidence`.
