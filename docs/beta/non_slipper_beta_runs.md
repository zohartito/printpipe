# Non-Slipper Beta Runs

Status: Wave 9 software run plan for beta coverage beyond the slipper fixture.

This plan uses the existing small STL fixtures so the beta pass can exercise
multiple object classes without adding large mesh assets. It is a software
artifact regression plan, not a substitute for physical printing. A passing run
folder proves that PrintPipe accepted the fixture, copied the input, and wrote
receipts and reports. It does not prove printability, final orientation quality,
surface quality, support burden, slicer success, or real-world part usefulness.

## Common Commands

Run each fixture through the current CLI run-folder path:

```bash
printpipe run tests/fixtures/objects/figurine/simple_figurine_ascii.stl --runs-dir runs/beta/non-slipper
printpipe run tests/fixtures/objects/cup_vase/cup_vase_open_frustum.stl --runs-dir runs/beta/non-slipper
printpipe run tests/fixtures/objects/flat_bracket/flat_bracket.stl --runs-dir runs/beta/non-slipper
printpipe run tests/fixtures/objects/decorative_organic/asymmetric_leaf_shell.stl --runs-dir runs/beta/non-slipper
printpipe run tests/fixtures/objects/existing_stl_pipeline/tiny_tetrahedron.stl --runs-dir runs/beta/non-slipper
```

Run the focused fixture checks that define each object's current regression
contract:

```bash
.venv/bin/python -m pytest tests/test_object_fixture_figurine.py
.venv/bin/python -m pytest tests/test_object_fixture_cup_vase.py
.venv/bin/python -m pytest tests/test_object_fixture_flat_bracket.py
.venv/bin/python -m pytest tests/test_object_fixture_decorative_organic.py
.venv/bin/python -m pytest tests/test_existing_stl_pipeline_bundle.py
```

## Expected Software Artifacts

Each `printpipe run` command should create one run directory under
`runs/beta/non-slipper/` with the current skeleton pipeline artifacts:

- `manifest.json`
- `00_input/`
- `10_frames/`
- `80_reports/run_report.json`
- `80_reports/run_report.md`
- `80_reports/run_report.html`

For the existing STL fixture, `.venv/bin/python -m pytest
tests/test_existing_stl_pipeline_bundle.py` also exercises the richer
existing-mesh pipeline path in a temporary run directory and expects a
Bambu-native bundle artifact under `60_bundle/`.

## Object Run Plan

### Figurine

Fixture: `tests/fixtures/objects/figurine/simple_figurine_ascii.stl`

Usefulness for regression:

- Covers a tall object with a base, feet, body, and head.
- Keeps semantic-upright risk visible: geometry can measure bounds and bed fit,
  but it cannot infer which side is the head or feet.
- Protects against regressions in ASCII STL parsing, metadata expectations, and
  default bed-fit candidate scoring.

Command:

```bash
printpipe run tests/fixtures/objects/figurine/simple_figurine_ascii.stl --runs-dir runs/beta/non-slipper
```

Expected software artifacts: the common run directory artifacts above, plus the
focused check from `.venv/bin/python -m pytest
tests/test_object_fixture_figurine.py`.

Physical printing required: verify upright presentation, base adhesion,
small-feature survival, support needs around protrusions, and whether the print
matches the intended figurine pose.

### Cup/Vase

Fixture: `tests/fixtures/objects/cup_vase/cup_vase_open_frustum.stl`

Usefulness for regression:

- Covers an open-rim object with a closed base and boundary edges at the mouth.
- Keeps cavity-direction risk visible: bed-fit success does not prove the
  opening faces upward.
- Protects topology expectations for open meshes, including boundary edge
  counts and no non-manifold edges.

Command:

```bash
printpipe run tests/fixtures/objects/cup_vase/cup_vase_open_frustum.stl --runs-dir runs/beta/non-slipper
```

Expected software artifacts: the common run directory artifacts above, plus the
focused check from `.venv/bin/python -m pytest
tests/test_object_fixture_cup_vase.py`.

Physical printing required: verify the mouth orientation, wall behavior,
interior quality, base adhesion, and whether slicer support choices make sense
for an open vessel.

### Flat Bracket

Fixture: `tests/fixtures/objects/flat_bracket/flat_bracket.stl`

Usefulness for regression:

- Covers a long, thin mechanical shape whose 0 degree footprint is too long for
  a 256 mm square bed but whose 45 degree Z rotation can fit.
- Keeps rotate-to-fit behavior visible without relying on semantic object
  recognition.
- Protects broad-face-down assumptions, XY footprint checks, and bed-fit
  candidate scoring for practical flat parts.

Command:

```bash
printpipe run tests/fixtures/objects/flat_bracket/flat_bracket.stl --runs-dir runs/beta/non-slipper
```

Expected software artifacts: the common run directory artifacts above, plus the
focused check from `.venv/bin/python -m pytest
tests/test_object_fixture_flat_bracket.py`.

Physical printing required: verify dimensional accuracy, first-layer stability,
warping risk, functional face quality, and whether the chosen bed rotation is
usable on an actual printer.

### Decorative Organic

Fixture: `tests/fixtures/objects/decorative_organic/asymmetric_leaf_shell.stl`

Usefulness for regression:

- Covers asymmetric decorative geometry with a raised crest and side lobes.
- Keeps support-risk honesty visible: current bed-fit checks do not estimate
  overhangs, fragile protrusions, cosmetic underside damage, or presentation
  intent.
- Protects the metadata flag that marks this fixture as requiring future
  support-risk evaluation.

Command:

```bash
printpipe run tests/fixtures/objects/decorative_organic/asymmetric_leaf_shell.stl --runs-dir runs/beta/non-slipper
```

Expected software artifacts: the common run directory artifacts above, plus the
focused check from `.venv/bin/python -m pytest
tests/test_object_fixture_decorative_organic.py`.

Physical printing required: verify support scars, fragile edge survival,
presentation orientation, overhang quality, and whether the underside is
acceptable for a decorative object.

### Existing STL

Fixture: `tests/fixtures/objects/existing_stl_pipeline/tiny_tetrahedron.stl`

Usefulness for regression:

- Covers imported STL preservation through the existing-mesh route.
- Protects the run spine that copies the source mesh, writes receipts and
  reports, imports the mesh into `20_meshgen/`, and creates a Bambu 3MF bundle
  in the focused pipeline test.
- Keeps the distinction clear between an imported source mesh and a fully
  repaired, oriented, profile-tuned, slice-verified object.

Command:

```bash
printpipe run tests/fixtures/objects/existing_stl_pipeline/tiny_tetrahedron.stl --runs-dir runs/beta/non-slipper
```

Focused bundle command:

```bash
.venv/bin/python -m pytest tests/test_existing_stl_pipeline_bundle.py
```

Expected software artifacts: the common run directory artifacts above from the
CLI command. The focused bundle test should additionally prove temporary-run
creation, imported mesh storage, `80_reports/` JSON/Markdown/HTML reports, and
`60_bundle/` Bambu 3MF creation and validation.

Physical printing required: verify that a real imported STL survives repair,
orientation, profile selection, slicing, and printer execution. The tiny
tetrahedron is intentionally too small and synthetic to count as a meaningful
real-world print sample.

## Beta Pass Criteria

For this non-slipper beta set, a software pass means:

- all five `printpipe run` commands complete with exit code 0
- each run folder has the expected manifest, input copy, skipped/accepted stage
  receipts, and JSON/Markdown/HTML reports
- each focused fixture test passes
- `tests/test_existing_stl_pipeline_bundle.py` validates the current 3MF bundle
  path for the existing STL fixture

Physical printing required before claiming object beta success:

- slice each object with the intended Bambu printer, filament, and process
  settings
- inspect slicer warnings, support decisions, time, mass, and bed placement
- print at least one representative object from each risk class: semantic
  upright, open vessel, long flat mechanical, decorative organic, and imported
  existing STL
- record observed failures as future regression fixtures or documented
  unsupported cases

Until those physical gates are complete, this document should describe the set
as software regression coverage only. It is useful beta preparation, but it is
not evidence that the objects are print-ready.
