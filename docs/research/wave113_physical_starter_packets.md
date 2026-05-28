# Wave 113 - Physical Starter Packet Handoff

## What Changed

Created local starter packets for the three physical-validation material families:

- `runs/physical-pla-validation/90_physical/physical_evidence.json`
- `runs/physical-petg-validation/90_physical/physical_evidence.json`
- `runs/physical-tpu-validation/90_physical/physical_evidence.json`

These run folders are ignored by git. They are local print-day handoff files, not committed evidence.

## Honesty Check

Each packet has:

- `print_status=not_printed`
- operator `Zohar`
- material/printer/object context
- notes saying the starter packet is not passed evidence

`printpipe physical-status --runs-dir runs --json` still reports all three families as `recorded_but_not_passed`.

## Markdown Copy Fix

Starter Markdown previously showed `No missing required evidence` under Open Issues when a packet was complete but still `not_printed`. That was data-correct but human-misleading. The renderer now writes:

- `Physical print not recorded yet`

for non-printed packets.

## Next Action

`printpipe final-plan --release-dir dist/release --runs-dir runs --regression-manifest regressions/dogfood_failures.json --json` now points to the PLA `record-physical-evidence` command as the next action.

## Boundary

This does not complete physical validation. F9 remains partial until real PLA, PETG, and TPU prints are recorded with observations and photo artifacts.
