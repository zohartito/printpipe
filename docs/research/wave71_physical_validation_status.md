# Wave 71 - Physical Validation Status Scanner

Date: 2026-05-28

## Why

Wave 70 made physical evidence portable in reports, but there still was not one
command that answered the beta question: do we have credible passed physical
evidence for the required material families yet?

The beta gate needs that answer without mixing software artifacts with real
print proof. A generated coupon, `.3mf`, slice receipt, or Bambu bundle can be
excellent software evidence, but the release gate should only pass when a real
packet says the coupon/object was printed and includes the material-family
inspection fields.

## What changed

- Added `printpipe.beta.physical_status`.
- Added `build_physical_validation_status()` for scanning run folders.
- Added `render_physical_validation_status()` for human-readable summaries.
- Added `printpipe physical-status --runs-dir runs`.
- Added `--json` for machine-readable gating.
- Added `--strict`, which exits `2` until required families pass.

## Status model

- `passed`: at least one packet has `print_status=passed` and no missing
  required evidence fields.
- `missing`: no packet was found for that material family.
- `incomplete`: a packet exists, but the best available packet is missing
  required evidence fields.
- `recorded_but_not_passed`: packets exist, but none are a credible pass.

Default required material families:

- PLA
- PETG
- TPU

## Boundaries

- The scanner reads `90_physical/physical_evidence.json`; it does not edit
  packets.
- It does not infer success from photos, generated coupon artifacts, slice
  receipts, or `.3mf` files.
- It intentionally fails strict mode until real passed evidence exists for every
  required family.

## Verification

Focused red/green target:

```bash
.venv/bin/pytest tests/test_beta_physical_status.py
```

The new tests first failed because `printpipe.beta.physical_status` did not
exist, then passed after the scanner and CLI command were implemented.
