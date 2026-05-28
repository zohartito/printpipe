# Wave 125 - Non-Destructive Physical Coupon Slice Command

## Purpose

Wave 124 made `physical-start --slice` possible, but already-started physical validation packets should not need to be recreated just to add a slice receipt. This wave adds a focused slice command for existing coupon bundles.

## What changed

- Added `printpipe physical-slice`.
- Added `slice_physical_validation_coupon()` for programmatic use.
- Reused the same Bambu CLI slice wrapper and `70_slice/slice_result.json` receipt path as normal runs.
- Physical plans now emit a `slice:` command when a coupon bundle exists but no slice receipt exists.
- `physical-start --slice` now shares the same lower-level coupon-bundle slice helper.

## Boundary

`physical-slice` is non-destructive software verification. It does not rewrite `90_physical/physical_evidence.json`, and it does not prove the coupon was printed. Physical validation still requires a real print, real observations, and an existing photo artifact.
