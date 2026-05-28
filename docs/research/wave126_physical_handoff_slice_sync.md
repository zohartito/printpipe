# Wave 126 - Physical Handoff Slice Receipt Sync

## Purpose

After Wave 125, existing physical validation coupon bundles could be sliced without recreating starter packets. The remaining mismatch was the Markdown handoff sheet: if slicing happened after `physical-start`, the handoff still said no slice receipt was generated.

## What changed

- `physical-slice` now refreshes the `## Slice Receipt` block in `90_physical/physical_print_handoff.md`.
- The refresh replaces an existing slice block or inserts one before the validation checklist.
- `90_physical/physical_evidence.json` is not rewritten.
- Terminal output now prints the handoff path after slicing.

## Boundary

This improves print-day handoff accuracy only. A synchronized handoff and a successful Bambu slice are still software evidence, not physical proof. Physical validation still requires a real coupon print, real observations, and an existing photo artifact.
