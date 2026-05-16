# Wave 5 Figurine Fixture

Status: added

Roadmap item 104 now has a small object fixture at
`tests/fixtures/objects/figurine/simple_figurine_ascii.stl`.

## Fixture Shape

The STL is dependency-light ASCII text and uses only triangular facets that the
current `read_ascii_stl` mesh adapter can parse. The model is intentionally
crude: a rectangular base, two block feet, a block body, and a block head.

Expected bounds:

- width: 16 mm
- depth: 10 mm
- height: 34 mm

## Orientation Notes

The companion metadata file records the intended semantic pose:

- upright figurine
- base down on the bed
- semantic orientation required before trusting geometry-only axes
- PCA alone may be wrong for figurines because sparse facets and mass
  distribution do not prove which surface is the base

## Verification

`tests/test_object_fixture_figurine.py` checks that the ASCII STL parses into
`MeshGeometry`, the metadata carries the orientation expectations, and default
candidate bed-fit scoring runs against a 256 mm by 256 mm bed without errors.
