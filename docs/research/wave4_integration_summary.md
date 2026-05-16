# Wave 4 Integration Summary

Status: complete

Wave 4 migrated the slipper proof-of-concept into PrintPipe as reusable code paths, fixtures, and external artifact references. The important choice was not to copy the heavy slipper STL/GLB/3MF artifacts into this repo. Instead, PrintPipe keeps a manifest that references them and uses small fixtures for repeatable tests.

## Outputs

- `src/printpipe/mesh/repair.py`: optional `trimesh`-based repair API following the slipper repair sequence when the dependency is installed.
- `src/printpipe/bambu/profiles/sources.py`: profile source discovery, indexing, lookup, and copy helpers.
- `src/printpipe/bambu/threemf/mesh_adapter.py`: dependency-light ASCII STL to `MeshGeometry` adapter and bundle writer.
- `src/printpipe/pipeline/__init__.py`: existing-mesh pipeline orchestrator skeleton.
- `tests/fixtures/bambu/slice_logs/slipper_v3_summary.log`: compact slipper v3 slice estimate fixture.
- `examples/slipper_poc_manifest.json`: external artifact manifest for the slipper POC.
- `docs/research/wave4_slipper_migration.md`: comparison between current PrintPipe capabilities and slipper v3 requirements.

## Verification

Full suite:

```text
.venv/bin/python -m pytest
84 passed, 2 skipped
```

The two skipped tests are intentional live repair smoke tests that require `trimesh`, which is not installed in the new app venv yet.

## Honest Limitations

- Real mesh repair is implemented behind an optional dependency, not guaranteed in the base install.
- Existing-mesh pipeline imports and reports, but it does not yet run repair, geometry, 3MF bundling, or slicing end to end.
- STL adapter only supports simple ASCII STL, not binary STL, GLB, OBJ, or 3MF mesh extraction.
- Slipper POC is a referenced external regression source, not a fully reproduced app run yet.
- Profile source discovery can find/load/copy profiles, but material rules are still not implemented.

## Next Gate

Wave 5 should expand from slipper-specific validation into generic object fixtures and stronger object/geometry behavior:

1. simple figurine fixture and expected orientation notes
2. cup/vase fixture and opening/upright notes
3. flat bracket/wrench fixture and bed-fit notes
4. decorative organic fixture and support-risk notes
5. existing STL end-to-end fixture through the current pipeline
6. cross-object orientation review that states what is still heuristic vs reliable

