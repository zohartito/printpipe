# Wave 5 Cross-Object Orientation Review

Status: foundation for roadmap item 112

Roadmap item 112 is "Compare all outcomes" across the Phase 13 dogfood
objects. This review narrows that comparison to orientation behavior so later
fixtures and run receipts can separate proven geometry behavior from object
understanding that is still missing.

## Current Heuristic Baseline

The current dependency-light geometry core supports simple, auditable
orientation mechanics:

- reliable: bounds, bed fit, and Z drop are reliable for the vertex data they
  receive. `compute_bounds` reports axis-aligned extents, `fits_bed` compares
  the footprint to the selected bed, and `center_xy_drop_z` translates the
  minimum Z to the bed plane.
- reliable: Z-axis rotation candidates are reliable as mechanical transforms.
  They can find a better XY footprint for a model that is already upright.
- partial: flat base detection is only a low-Z vertex concentration diagnostic.
  It can suggest bed contact, but it does not prove a planar face, contact
  area, stability, or semantic correctness.
- unsolved: semantic upright is not detected. The code cannot tell head from
  feet, sole from upper, front from back, or intended display orientation.
- unsolved: cavity opening direction is not detected. The code cannot prove a
  cup/vase mouth is open upward or that an internal cavity is printable.
- unsolved: support burden is not scored. The code does not estimate overhang
  angle, island risk, slicer support needs, or cosmetic support damage before
  slicing.

## Cross-Object Comparison

| Object category | What current heuristics can do | Orientation risk |
| --- | --- | --- |
| Slipper | Bounds, bed fit, Z drop, and Z rotations are reliable for footprint placement. A sole-like flat region may make the flat-base diagnostic useful, but only as partial evidence. | Semantic upright is unsolved: the generic code does not know sole down, toe direction, or upper/strap intent. Support burden under arches or straps is also unsolved until later geometry or slice evidence exists. |
| Figurine | Bounds, bed fit, Z drop, and Z rotations are reliable once a figurine is already upright. A plinth or large feet may be partial flat-base evidence. | Semantic upright is the core unsolved risk. The current pipeline cannot distinguish standing from lying sideways or upside down, and it does not score support burden for arms, hair, weapons, or other overhangs. |
| Cup/vase | Bounds, bed fit, Z drop, and Z rotations are reliable for footprint and bed placement. A broad bottom can provide partial flat-base evidence. | Cavity opening direction is unsolved. The pipeline cannot tell whether the mouth faces up, down, or sideways, and it does not reason about inside support burden or trapped openings. |
| Flat bracket | Bounds, bed fit, Z drop, and Z rotations are reliable and likely cover the most important placement behavior for thin mechanical parts. Flat base evidence is still formally partial, but this category is the best match for the current heuristic set. | Semantic upright is usually low importance, but the code still cannot reason about named functional faces, countersinks, toleranced surfaces, or preferred cosmetic face orientation. |
| Decorative organic | Bounds, bed fit, Z drop, and Z rotations remain reliable as transforms and measurements, but they may place the object on a tiny low point rather than a stable surface. Flat-base evidence is partial and often low value for irregular geometry. | Semantic upright and support burden are both unsolved. Organic shapes can have many local minima, fragile protrusions, and aesthetic faces that the current heuristics do not understand. |
| Existing STL pipeline | Bounds, bed fit, Z drop, and Z rotations are reliable for imported STL vertices, including the current ASCII STL adapter path. The pipeline can preserve user-provided orientation as a starting point. | Existing STL import does not solve orientation by itself. It inherits whatever orientation the source mesh has, while flat base remains partial and semantic upright, cavity opening, and support burden remain unsolved. |

## Item 112 Acceptance Criteria

Item 112 can be treated as complete only when the comparison is evidence-backed,
not just described in prose:

- The comparison covers slipper, figurine, cup/vase, flat bracket, decorative
  organic, and existing STL pipeline cases in one matrix.
- Each case has a fixture, external artifact reference, or run folder receipt
  that records input type, mesh source, selected printer/bed, target size if
  applicable, candidate orientations, chosen transform, bed-fit result, and
  final outcome.
- The report labels each orientation decision as reliable, partial, or
  unsolved using the current heuristic vocabulary above.
- Bounds, bed fit, and Z drop are considered passing only when their recorded
  metrics match the selected Bambu bed and transformed mesh.
- Flat base is accepted only as partial evidence unless a later detector proves
  planar support area and stability.
- Semantic upright, cavity opening, and support burden are not claimed as solved
  without dedicated detectors, slicer-derived evidence, or explicit
  user-provided intent.
- A failed object run still counts as a useful item 112 outcome if it has a
  complete failed-run receipt and identifies the failing gate precisely.
- The final item 112 summary states which failures became regression fixtures
  and which cases are documented unsupported cases for the current milestone.

## Near-Term Implications

The next implementation work should keep orientation receipts honest. The
current foundation can safely answer "does this transformed mesh fit and sit on
the bed?" It should not answer "is this object upright, open correctly, stable,
or low-support?" until those capabilities are added and tested across the same
six object categories.
