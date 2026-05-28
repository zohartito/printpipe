# Wave 13 Integration Summary

Wave 13 connected the existing-STL path into the normal CLI and local web flow. This is still not the full reference-image-to-mesh product, but it removes a major fake-success gap: an existing mesh run now produces the same kinds of artifacts the app promises to manage.

## What changed

- `printpipe run input.stl` now runs input classification, existing-mesh import, optional `trimesh` repair, orientation, bed-fit preview generation, Bambu `.3mf` bundling, bundle validation, slice receipt recording, and final reports.
- Local web STL uploads now use the same existing-mesh pipeline instead of stopping at input preparation.
- Mesh repair now exports repaired STL output as ASCII STL, so the current dependency-light orientation and bundling adapters can consume the repaired mesh directly.
- Failed repair is a hard stop before orientation and bundling. The run still gets JSON, Markdown, and HTML reports with the failed repair receipt.
- The Bambu CLI slice stage reports a clean failed receipt if the requested executable cannot start.
- HTML reports now embed preview artifacts, highlight `.3mf` bundles with download links, and render generated pre-print checklist items.

## What worked

- The existing-STL regression fixture now exercises repair -> orientation -> bed fit -> bundle -> validation as one run.
- Web artifact discovery now finds oriented meshes, slice result JSON, Bambu logs, contact-sheet previews, bed-fit SVG previews, and `.3mf` bundles.
- The pre-print checklist gives TPU-specific reminders when the material context says TPU, including drying, external spool path, first-layer inspection, and flex-coupon validation.

## What still has to stay partial

- Live Bambu CLI slicing remains partial until a real Bambu Studio executable is deliberately invoked and the resulting slice logs are captured.
- Superseded by Wave 23: image/GIF/video mesh generation is now wired through the configured Hunyuan3D adapter in the normal orchestrator.
- Physical slipper, TPU, PLA, PETG, and beta-user validation remain partial until there are printed parts, photos, measurements, and failure notes.
- The web app can download `.3mf`; one-click opening in Bambu Studio is not implemented.

## Verification

- Focused integration verification: `54 passed, 1 skipped`.
- Additional CLI/web/slice repair hardening verification: `42 passed`.
- Full-suite verification passed after this document update.
