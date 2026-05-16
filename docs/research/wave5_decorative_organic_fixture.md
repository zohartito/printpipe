# Wave 5 Decorative Organic Fixture

Roadmap item: 107, decorative organic object.

## Fixture

- `tests/fixtures/objects/decorative_organic/asymmetric_leaf_shell.stl`
- `tests/fixtures/objects/decorative_organic/expected_metadata.json`

The STL is a small ASCII-only low-poly shell with an asymmetric perimeter, a raised crest, and side lobes that hint at overhang risk. It is intentionally crude and human-readable so it can act as a regression fixture without adding large mesh assets to the repo.

## Support-Risk Notes

This object is meant to document a gap in the current orientation pipeline. A bed-fit-only pass can say every tested Z rotation fits on the plate, but that does not answer whether the visible presentation creates unsupported decorative lobes or a poor underside.

Expected future behavior:

- keep visual-orientation intent separate from printability scoring
- add support-risk scoring for overhang-like organic forms
- avoid treating bed-fit success as an orientation acceptance gate by itself

The metadata includes `requires_future_support_risk_evaluation: true` so future object-understanding work can discover this fixture and promote it into a support-risk regression when roadmap item 65 is implemented.
