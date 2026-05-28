# Wave 130 - Final Readiness Row Artifact Links

## Purpose

The top next-action panel already surfaced all important physical validation files, but the individual PLA/PETG/TPU rows only showed the coupon STL and handoff. This made the rows less useful if Zohar is working through the checklist family by family.

## What changed

- Final-readiness action rows now keep:
  - `bundle_path`
  - `bundle_validation_path`
  - `slice_result_path`
- The web checklist renders row-level Bundle, Bundle validation, and Slice receipt paths.

## Boundary

These are artifact and receipt links only. They do not prove the coupon was printed or that the material passed physical validation.
