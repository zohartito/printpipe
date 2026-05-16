# Wave 5 Cup/Vase Fixture

Status: added for roadmap item 105

## Scope

This fixture adds a small dependency-light cup/vase-style object for object
understanding regression tests. It is intentionally a tiny ASCII STL rather than
a realistic model so the geometry remains reviewable in Git and parseable by
the current `read_ascii_stl` adapter.

## Fixture

- `tests/fixtures/objects/cup_vase/cup_vase_open_frustum.stl`
- `tests/fixtures/objects/cup_vase/expected_metadata.json`

The mesh is a six-sided open frustum with a closed base and no top cap. The top
rim is deliberately open, so the topology scan should report boundary edges
instead of treating the object as watertight.

## Expected Geometry

- Bounds: 32 mm X by 28 mm Y by 30 mm Z.
- Vertices after adapter de-duplication: 13.
- Triangles: 18.
- Boundary edges: 6, corresponding to the open rim.
- Non-manifold edges: 0.
- Bed fit: fits comfortably on a 128 mm by 128 mm bed with a 5 mm margin.

## Orientation Notes

The intended semantic orientation is upright with the opening up and base down.
This is a useful regression case because simple bed-fit scoring alone cannot
prove that a cup or vase is printable in the intended orientation. Future object
understanding needs cavity/opening detection before it can make a reliable
automatic orientation choice for this class of object.

## Verification

The focused test is:

```text
.venv/bin/python -m pytest tests/test_object_fixture_cup_vase.py
```
