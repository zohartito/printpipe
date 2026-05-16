# Wave 5 Integration Summary

Status: complete

Wave 5 expanded PrintPipe beyond the slipper proof-of-concept with small, human-readable object fixtures. These fixtures are not meant to be beautiful models. They are regression probes that force the app to confront different orientation and printability classes.

## Outputs

- `tests/fixtures/objects/figurine/`: upright semantic-orientation fixture.
- `tests/fixtures/objects/cup_vase/`: open-cavity/upright fixture.
- `tests/fixtures/objects/flat_bracket/`: long flat object where diagonal bed fit matters.
- `tests/fixtures/objects/decorative_organic/`: asymmetric decorative object requiring future support-risk scoring.
- `tests/fixtures/objects/existing_stl_pipeline/`: existing STL import-to-3MF bundle fixture.
- `docs/research/wave5_cross_object_orientation_review.md`: compares all object categories and separates reliable, partial, and unsolved geometry behavior.

## Verification

Full suite:

```text
.venv/bin/python -m pytest
98 passed, 2 skipped
```

The two skipped tests are still the optional `trimesh` live repair checks.

## What Is Now True

- PrintPipe has generic object fixtures beyond the slipper.
- ASCII STL fixtures can be parsed into `MeshGeometry`.
- Existing STL can flow through run creation, mesh import, reporting, and Bambu-native 3MF bundle creation.
- Bed-fit scoring has a regression case where 0 degrees fails and 45 degrees fits.
- The docs explicitly identify that semantic upright orientation, cavity detection, and support burden remain unsolved.

## Honest Limitations

- These fixtures are synthetic and tiny; they do not prove production meshgen quality.
- No real image/GIF/video-to-mesh path is implemented yet.
- No real Bambu slice has been run from these fixtures.
- Support-risk scoring is documented but not implemented.
- Material tests for TPU/PLA/PETG remain pending.

## Next Gate

Wave 6 should implement filament/material rule foundations:

1. PLA rules.
2. PETG rules.
3. TPU rules.
4. ABS/ASA rules.
5. PC/PA rules.
6. Settings reason catalog.

