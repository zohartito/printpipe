# Wave 103 Physical Evidence UI Hardening

Status: complete for run-detail UI visibility. This is not physical print proof.

## Finding

The live repo already loaded `90_physical/physical_evidence.json` in the run-detail contract and displayed a Physical Evidence panel. The remaining gap was visibility and state coverage: the panel did not show material, printer, or timestamps, and tests did not cover all packet states.

## Change

- Added run-detail contract and web coverage for no packet, `not_printed`, `partial`, `failed`, `passed`, missing required fields, and artifact links.
- Updated the run-detail Physical Evidence panel to show operator, material, printer, started timestamp, completed timestamp, missing required evidence, JSON/Markdown packet links, and physical artifact links.
- Verified incomplete and `not_printed` packets remain honest and do not become physical-validation proof.

## Boundary

The UI still treats physical evidence as a recorded packet, not as a global material-validation pass. PLA/PETG/TPU material gates still require actual passed physical evidence packets, and trusted-user beta remains separate.
