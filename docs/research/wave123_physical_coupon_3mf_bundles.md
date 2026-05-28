# Wave 123 - Physical Coupon 3MF Bundles

## Purpose

Physical validation was still too manual. `physical-start` generated a coupon STL and handoff, but the user still had to import the STL into Bambu Studio and manually trust the profile context. For the final physical gate, the starter packet should include a ready-to-open Bambu `.3mf` bundle with material-aware settings.

## What changed

- `physical-start` now writes:
  - `40_geometry/physical_validation_coupon_40x15x3.stl`
  - `40_geometry/physical_validation_coupon_40x15x3.json`
  - `60_bundle/physical_validation_coupon_40x15x3.3mf`
  - `60_bundle/physical_validation_coupon_40x15x3_bundle_validation.json`
  - `90_physical/physical_print_handoff.md`
- The `.3mf` uses PrintPipe's existing material-aware Bambu profile resolution path.
- Bundle validation checks the archive members and Bambu `Application` metadata signature.
- Physical plans now surface `bundle_path` and `bundle_validation_path` for started coupon packets.
- Human CLI output prints the new bundle paths.

## Boundary

The generated `.3mf` is still digital prep. Physical validation only passes after a real coupon print is recorded with real observations and an existing photo artifact.
