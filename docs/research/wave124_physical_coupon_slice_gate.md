# Wave 124 - Optional Physical Coupon Slice Gate

## Purpose

The physical-validation starter packet now creates a Bambu-ready coupon `.3mf`, but the physical gate benefits from an explicit slice receipt before the user prints. This wave adds that receipt path without making Bambu Studio a hard dependency for creating starter packets.

## What changed

- Added `physical-start --slice`.
- Added `physical-start --bambu-cli <path>` for explicit Bambu Studio CLI selection.
- `--bambu-cli` now requires `--slice`.
- When slicing is requested, the starter packet writes `70_slice/slice_result.json` using the existing Bambu CLI slice wrapper.
- `physical-start --json` returns:
  - `slice_requested`
  - `slice_status`
  - `slice_message`
  - `slice_result_path`
- Physical plans and final-next can surface `slice_result_path` when present.

## Boundary

Slice receipts are software evidence. They do not prove adhesion, layer bonding, flex recovery, support removal, or any other physical print result. PLA, PETG, and TPU still require real evidence packets with real observations and an existing photo artifact.
