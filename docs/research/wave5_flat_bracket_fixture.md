# Wave 5 Flat Bracket Fixture

Status: complete

Roadmap item 106 now has a compact ASCII STL fixture for a long, flat bracket/wrench-like object. The fixture is intentionally simple: a 300 mm long, 60 mm wide, 4 mm tall tapered prism. It is not meant to test semantic recognition of a real wrench jaw; it is meant to prove that the current geometry path can parse a small human-readable STL, keep the broad face down, and score XY rotations for bed fit.

## Fixture Files

- `tests/fixtures/objects/flat_bracket/flat_bracket.stl`
- `tests/fixtures/objects/flat_bracket/expected_metadata.json`
- `tests/test_object_fixture_flat_bracket.py`

## Orientation Notes

- The broad face is the intended flattest face down.
- The long axis should be allowed to rotate around Z for bed fit.
- Semantic understanding is less critical than bed-fit scoring for this fixture.
- On a 256 x 256 mm test bed, the 0 degree pose does not fit because the long axis is 300 mm. The 45 degree candidate fits because the diagonal footprint is reduced enough for the square bed.

## Verification

The focused fixture test checks that:

- the ASCII STL parses through the Wave 4 `read_ascii_stl` adapter into `MeshGeometry`
- the Z height is small relative to the longest XY axis
- `candidate_rotations` includes a 45 degree candidate that fits on the test bed while 0 degrees does not

