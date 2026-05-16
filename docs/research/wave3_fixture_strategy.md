# Wave 3 Fixture Strategy

Wave 3 Agent F lays the foundation for roadmap items 103-112 without adding
large binary assets. The goal is not to prove every Phase 13 object yet. The
goal is to make the regression path explicit and give later agents small,
parseable fixtures for topology and slicer warning contracts.

## Fixture Layout

Current tiny fixtures live under `tests/fixtures/`:

- `meshes/topology/watertight_tetrahedron.json`
- `meshes/topology/open_mesh_boundary.json`
- `meshes/topology/non_manifold_edge.json`
- `bambu/slice_logs/non_manifold_warning.log`
- `bambu/slice_logs/boundary_off_bed_warning.log`
- `bambu/slice_logs/enum_replacement_warning.log`
- `bambu/slice_logs/floating_cantilever_warning.log`
- `bambu/slice_logs/success_estimate.log`

The topology fixtures are JSON because topology gates need structured faces and
expected counts. The slicer fixtures are short text logs because the first slice
parser should prove that it can classify real CLI messages before full Bambu
run folders are added.

## Failed Run To Regression

Every failed real run should become a regression fixture before the fix is
considered complete.

1. Preserve the original run folder outside normal unit-test fixtures if it is
   large.
2. Record a manifest with command, platform, Bambu Studio version, printer,
   filament, provider, random seed when available, artifact hashes, first
   failing gate, observed message, and expected future behavior.
3. Minimize the failure into the smallest repo-safe fixture that still fails for
   the same reason.
4. Add or update a test that loads the minimized fixture and asserts the gate,
   parser, or report behavior.
5. Keep the minimized fixture after the fix lands.

Large meshes, videos, `.3mf` bundles, and G-code files should not be committed
directly unless they are intentionally tiny. Prefer derived JSON topology,
trimmed slicer logs, profile snippets, hashes, and manifests. When a full
artifact is needed for manual reproduction, keep it in an external artifact
store or local preserved run path and reference it by hash in the manifest.

## Roadmap 103-112 Foundation

The Phase 13 object matrix needs both object coverage and material coverage:
slipper, figurine, cup or vase, bracket or wrench-like object, decorative
organic object, existing STL import, TPU, PLA, and PETG. Each case should end
with a comparable outcome row:

- input kind and source
- material and printer profile
- first failing gate or final slice success
- topology summary before and after repair
- slice warning class, if any
- estimate fields when slicing succeeds
- artifact hashes for the run folder

The fixtures added in this wave are deliberately synthetic. They give later
agents stable cases for common blockers: watertight success, boundary edges,
non-manifold edges, off-bed placement, enum replacement, floating cantilever
warnings, and a successful slice estimate.

## Acceptance Policy

A new fixture should be accepted only when it is named for the behavior it
exercises, small enough for normal test runs, parseable by a focused test, and
tied to a documented gate. Do not add a fixture just because a file exists in a
run folder. Add it because it catches a known failure mode or protects a
roadmap acceptance criterion.
