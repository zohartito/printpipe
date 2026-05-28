# Wave 122 - Physical Next Action Honesty

## Purpose

`final-next` was technically correct but too easy to misuse after a physical starter packet existed: it selected the post-print `record-physical-evidence` command even when the packet still said `not_printed` and the photo path was a placeholder. At the time, that command also preselected `--print-status passed`; Wave 141 later replaced that with the explicit `--print-status "<passed|failed|partial>"` placeholder.

The real next action in that state is to open the run folder, print the coupon STL, follow the handoff, take a real photo, and only then record evidence.

## What changed

- Physical plan actions now include clearer `detail` copy per state.
- Started-but-not-printed coupon actions now include:
  - `command=printpipe open-folder "<run>" --target run`
  - `command_kind=print_handoff_command`
- `record_command` remains available as the post-print command.
- Terminal physical-plan output now distinguishes:
  - `next`
  - `record after print`
- Final-readiness web command selection now matches final-plan priority by preferring explicit `command` before `record_command`.

## Boundary

This still does not close physical validation. PLA, PETG, and TPU require real printed coupons or objects plus existing photo artifacts and material-specific observations before the gate can pass.
