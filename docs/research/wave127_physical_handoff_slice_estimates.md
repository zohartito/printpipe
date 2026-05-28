# Wave 127 - Physical Handoff Slice Estimates

## Purpose

The physical validation handoff now points to the slice receipt, but the human print-day sheet should also show the basic estimate directly. This avoids making Zohar open JSON just to see how long the coupon should take.

## What changed

- `physical-slice` now exposes slice estimate fields in its JSON payload:
  - `slice_time_seconds`
  - `slice_filament_g`
  - `slice_layer_count`
  - `slice_cost`
- The handoff `## Slice Receipt` section now includes a compact estimate line.
- Re-running `physical-slice` refreshed the local PLA, PETG, and TPU handoffs with current estimates.

## Boundary

The estimate is slicer/software evidence only. It does not prove adhesion, layer bonding, flex recovery, release behavior, or any other physical print result.
