# Wave 102 Failure Regression Coverage

Status: complete for current software dogfood failures. This does not complete
trusted-user beta or physical printing.

## Problem

PrintPipe could record a failure packet and run a regression manifest, but it did
not prove that every captured failure had a matching regression case. That left
Phase 16 item 131 too easy to over-claim.

## Implementation

- Added `build_failure_regression_status()` in `printpipe.beta.regression`.
- Added `printpipe failure-regression-status`.
- Added a `failure_regressions` readiness gate.
- Made failure scanners recursive so nested run folders such as
  `runs/dogfood/<run-id>/90_beta/failure_report.json` are included.
- Added `regressions/dogfood_failures.json`.

## Captured Failures

Local ignored failure packets were written for:

| Source run | Failure | Regression case |
| --- | --- | --- |
| `20260528-143644-cup-vase-open-frustum` | `trimesh.repair.fill_holes()` crashed because `networkx` was missing. | `dogfood-cup-vase-networkx` |
| `20260528-143937-cup-vase-open-frustum` | Open-rim cup/vase remained non-watertight and repair failed despite the pipeline intending to allow it. | `dogfood-cup-vase-open-rim-repair` |
| `20260528-144139-flat-bracket` | Flat bracket bundled at 0 degrees even though bed-fit preview selected 45 degrees, so Bambu CLI saw an empty/off-bed plate. | `dogfood-flat-bracket-bed-fit-rotation` |

The committed manifest uses expected-success cases because these failures are
now fixed and should stay fixed.

## Verification

```bash
printpipe failure-regression-status --runs-dir runs --regression-manifest regressions/dogfood_failures.json --strict
printpipe run-regressions regressions/dogfood_failures.json --strict
```

Observed:

- `failure-regression-status`: `passed`, 3 / 3 captured failures covered.
- `run-regressions`: `passed`, 3 / 3 cases matched expected success.

## Boundary

These are software regression receipts. Physical material validation and
trusted-user beta still require external evidence from actual prints/users.
