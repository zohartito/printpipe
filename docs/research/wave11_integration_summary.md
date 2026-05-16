# Wave 11 Integration Summary

Status: complete as software integration; several stages remain intentionally
heuristic or placeholder until real dependencies, real slicing, and physical
prints are run.

## What Landed

Wave 11 closed a set of pipeline gaps:

- Input processing now extracts GIF/video frames through `ffmpeg` when present,
  stores extracted, cleaned, and selected reference folders, and writes a
  contact-sheet manifest.
- Background removal and lighting normalization now produce explicit receipt
  metadata, but they are copy/no-op stages rather than semantic image cleanup.
- Hunyuan3D is available as a local-command provider behind
  `PRINTPIPE_HUNYUAN3D_COMMAND`; it is disabled cleanly when no command is set.
- Geometry now has bounds-only primary-axis estimates, cavity/opening
  diagnostics, support-burden scoring, scale planning, scale-down/fail
  decisions, top orientation selection, and SVG/JSON bed-fit previews.
- Bambu/Orca profile discovery now searches likely app and user roots without
  hardcoded cloud user IDs, then summarizes filament defaults by type/material.
- Slice runs now emit stable `slice_result.json`, stdout/stderr log artifacts,
  optional G-code artifacts, and receipt metrics.
- The local web UI now accepts `POST /runs` multipart uploads, validates
  printer/material/target-size inputs, creates a skeleton run, prepares input
  artifacts, writes reports, and redirects to the HTML report.

## What Is Still Partial

- Mesh repair still depends on optional `trimesh`; the current environment did
  not have that package installed during this wave.
- Background removal and lighting normalization are honest placeholders.
- Contact sheet output is a JSON preview manifest, not a rendered image sheet.
- The main CLI/web flow prepares input and reports, but does not yet drive the
  complete meshgen -> repair -> orient -> bundle -> real Bambu slice chain.
- Real Bambu Studio CLI slicing and physical printer validation remain external
  gates.

## Verification

```text
.venv/bin/python -m pytest
228 passed, 2 skipped

git diff --check
passed
```
