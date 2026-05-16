# Wave 2 Integration Summary

Status: complete

Wave 2 created the first tested code skeleton for the PrintPipe pipeline. The modules are intentionally dependency-light: they define stable contracts, run-folder artifacts, receipts, and validation gates before adding heavy media, mesh, or slicer dependencies.

## Outputs

- `src/printpipe/contracts.py`: shared artifact, stage, input, mesh-stat, and receipt contracts.
- `src/printpipe/runs/paths.py`: immutable run-folder creation with manifest and stage directories.
- `src/printpipe/inputs/processor.py`: still-image, GIF, video, and existing-mesh routing with honest skipped receipts for unimplemented heavy processing.
- `src/printpipe/meshgen/`: provider contracts, existing-mesh provider, provider registry, placeholders, retry wrapper, and provider receipts.
- `src/printpipe/mesh/`: pure-Python topology edge counting, validation result, JSON stats export, and clear failure gate.
- `src/printpipe/bambu/profiles/`: JSON profile loading, inheritance resolution, settings delta normalization, and enum validation.
- `src/printpipe/bambu/threemf/`: minimal Bambu-native 3MF writer and structural validator.
- `src/printpipe/reports/`: JSON and Markdown run report writers.

## Verification

Full suite:

```text
.venv/bin/python -m pytest
42 passed
```

## Honest Limitations

- GIF/video frame extraction is not implemented yet.
- Background removal and lighting normalization are explicit skipped receipts.
- Mesh repair is not implemented yet; only topology validation and failure gates exist.
- Hunyuan3D is not implemented yet.
- Bambu/Orca default profile discovery is not wired to real installed/source profiles yet.
- 3MF bundling writes a minimal test mesh shape, not arbitrary repaired mesh conversion yet.
- Slice gate is not implemented yet.
- Reports are Markdown/JSON skeletons, not polished HTML.

## Next Gate

Wave 3 should connect these pieces into the verification spine:

1. Bambu CLI slice gate.
2. Settings delta report command/output.
3. Orientation and bed-fit scoring.
4. Report improvements.
5. `printpipe run` command wrapper.
6. Regression fixtures.

