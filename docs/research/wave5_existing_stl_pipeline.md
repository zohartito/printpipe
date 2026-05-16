# Wave 5 Existing STL Pipeline Fixture

Status: foundation for roadmap item 108

Roadmap item 108 is "Existing STL import test." This fixture proves the current
dependency-light existing-mesh path can move a small STL through run creation,
receipts, reports, imported mesh storage, and Bambu 3MF bundle writing.

## Fixture

- `tests/fixtures/objects/existing_stl_pipeline/tiny_tetrahedron.stl`
- `tests/fixtures/objects/existing_stl_pipeline/metadata.json`
- `tests/test_existing_stl_pipeline_bundle.py`

The STL is an ASCII-only tetrahedron with four vertices and four triangular
facets. It is deliberately tiny and human-readable, so it can stay in the repo
as a stable regression fixture without depending on large external meshes.

The metadata fixture records:

- roadmap item and fixture role
- object name used in the 3MF bundle
- expected vertex and triangle counts
- Bambu profile IDs for filament, process, printer, nozzle, model, and height
- target bundle filename and bed dimensions

## What Is End-to-End Now

The test now covers the following path:

1. `run_existing_mesh_pipeline` creates a run folder under a temp runs dir.
2. The source STL is copied into `00_input`.
3. Input classification and existing-mesh routing produce succeeded receipts.
4. `ExistingMeshProvider` imports the STL into `20_meshgen`.
5. JSON, Markdown, and HTML run reports are written under `80_reports`.
6. `read_ascii_stl` parses the imported STL into `MeshGeometry`.
7. `write_bundle_from_ascii_stl` writes a Bambu-native `.3mf` into `60_bundle`.
8. `validate_bundle` confirms the required 3MF members and Bambu Application
   metadata are present.
9. The test opens the 3MF and checks mesh counts plus the selected profile IDs.

This is enough to prove that the current existing-STL foundation can preserve
an imported STL artifact and feed it into the current bundle writer.

## What Remains

This is not a real print-ready existing-STL pipeline yet. The fixture
intentionally stops before these gates:

- Repair: no topology scan, repair operation, watertight validation, or repair
  stats are run as part of this end-to-end fixture.
- Orientation: the source mesh orientation is preserved. There is no primary
  axis detection, flat-base proof, support-burden scoring, or chosen orientation
  receipt.
- Scale and bed fit: the bundle uses a bed-center transform, but there is no
  target-size inference, scale decision, rotate-to-fit retry, or bed-fit
  visualization.
- Profile rules: the test uses fixture profile IDs directly. It does not load
  real profile source trees, apply filament/process override rules, or produce
  settings-delta reasons.
- Slice: no Bambu CLI slice is invoked, no G-code is produced, and no slice
  warning, time, mass, cost, or layer estimate is checked.

## Next Acceptance Step

Item 108 should move beyond foundation when an existing STL run has receipts for
repair, orientation, profile selection, bundle creation, and slice verification.
The current fixture should remain as the fast dependency-light smoke path, while
a later integration fixture can use a more realistic STL and skip cleanly when
Bambu Studio or optional mesh repair dependencies are not available.
