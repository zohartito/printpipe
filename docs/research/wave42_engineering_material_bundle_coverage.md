# Wave 42 - Engineering Material Bundle Coverage

Date: 2026-05-28

## Goal

Make sure the remaining material families with existing rule modules are real in
generated Bambu bundles, not just dropdown labels or settings-delta documents.

## Findings

- ABS/ASA and PC/PA/PA-CF rule modules already existed.
- The pipeline bundle selector did not import those rule modules, so materials
  like `ABS`, `PC`, and `PA-CF` still fell through to the Generic PLA bundle
  baseline.
- PETG exposed the same class of issue first: Bambu rejects some materials if the
  project defaults to Cool Plate.

## Changes

- Added ABS, ASA, PC, PA, and PA-CF branches in the bundle profile selector.
- All those branches now resolve the matching Generic Bambu filament profile when
  available and then apply PrintPipe's material overrides on top.
- Added `curr_bed_type=Textured PEI Plate` to ABS/ASA and PC/PA/PA-CF rules.
- Added bundle regression coverage using fake profile defaults that would stay
  PLA unless the material rules are actually applied.

## Live Slice Evidence

Command shape:

```bash
.venv/bin/printpipe run tests/fixtures/objects/existing_stl_pipeline/tiny_tetrahedron.stl \
  --runs-dir /tmp/printpipe-material-slice-<material>... \
  --material "<material>" \
  --slice \
  --bambu-cli /Applications/BambuStudio.app/Contents/MacOS/BambuStudio
```

Results:

| Material | Return | Warnings | Errors | Time | Filament | Layers |
| --- | ---: | --- | --- | ---: | ---: | ---: |
| ABS | 0 | `[]` | `[]` | 156 s | 0.31 g | 47 |
| ASA | 0 | `[]` | `[]` | 158 s | 0.31 g | 47 |
| PC | 0 | `[]` | `[]` | 166 s | 0.31 g | 47 |
| PA | 0 | `[]` | `[]` | 255 s | 0.33 g | 47 |
| PA-CF | 0 | `[]` | `[]` | 174 s | 0.36 g | 47 |

## Boundary

This completes software/slice evidence for these material families. It does not
prove real-world material performance, drying, adhesion, enclosure behavior,
support removability, or part strength. Those stay under the physical evidence
and beta loops.
