# Wave 114 - Physical Validation Coupon Artifacts

## Purpose

Wave 113 created honest `not_printed` physical starter packets, but the handoff still made Zohar infer which printable coupon artifact to use for PLA, PETG, and TPU validation. Wave 114 closes that software gap by generating the printable coupon STL/JSON sidecar as part of `physical-start` and surfacing those paths in `physical-plan` and the final-readiness UI.

## What changed

- `printpipe physical-start --family <family> --runs-dir runs --operator Zohar --json` now writes `40_geometry/physical_validation_coupon_40x15x3.stl`.
- The same command writes `40_geometry/physical_validation_coupon_40x15x3.json`.
- The JSON output now returns `coupon_stl_path` and `coupon_json_path`.
- `physical-plan` scans existing starter folders for those coupon artifacts and includes their paths in action payloads.
- The home-page final-readiness panel renders the coupon artifact path in physical-validation action rows.

## Material-specific coupon checks

- PLA: bed adhesion, first-layer continuity, dimension check, release after cooling.
- PETG: bed adhesion, first-layer continuity, warping check, stringing check.
- TPU: bed adhesion, flex recovery, interlayer bonding, support/brim removability.

## Local evidence generated

Ignored local starter folders now contain the printable coupon artifacts:

- `runs/physical-pla-validation/40_geometry/physical_validation_coupon_40x15x3.stl`
- `runs/physical-pla-validation/40_geometry/physical_validation_coupon_40x15x3.json`
- `runs/physical-petg-validation/40_geometry/physical_validation_coupon_40x15x3.stl`
- `runs/physical-petg-validation/40_geometry/physical_validation_coupon_40x15x3.json`
- `runs/physical-tpu-validation/40_geometry/physical_validation_coupon_40x15x3.stl`
- `runs/physical-tpu-validation/40_geometry/physical_validation_coupon_40x15x3.json`

## Verification

- `pytest tests/test_beta_physical_plan.py tests/test_final_readiness_web.py -q`
- `printpipe physical-start --family pla --runs-dir runs --operator Zohar --json`
- `printpipe physical-start --family petg --runs-dir runs --operator Zohar --json`
- `printpipe physical-start --family tpu --runs-dir runs --operator Zohar --json`
- `printpipe physical-plan --runs-dir runs --json`
- `printpipe physical-status --runs-dir runs --json`

## Boundary

These coupon artifacts are printable inputs and handoff receipts only. They are not physical proof. F9 and the physical validation gate remain partial until Zohar prints PLA, PETG, and TPU coupons or small objects, records observations, and attaches photo evidence.
