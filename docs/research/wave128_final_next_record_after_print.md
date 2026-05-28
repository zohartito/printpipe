# Wave 128 - Final Next Record-After-Print Command

## Purpose

`final-next` correctly points first at the physical print handoff folder, but agents and UI clients also need the exact evidence command for after the coupon is printed. Before this wave, that command was present in `physical-plan` and the handoff Markdown, but missing from the focused next-action payload.

## What changed

- `final-next --json` now includes `record_command` for print-handoff actions.
- Terminal `final-next` and `final-plan` render it as `record after print` when it differs from the immediate command.
- The web final-readiness panel renders a separate `Record after print` command block.
- Start/setup actions do not surface premature record commands.
- Physical handoff slice section spacing was normalized while refreshing local coupon handoffs.

## Boundary

The immediate command remains the honest next action: open the run folder and print the coupon. The record command is a post-print instruction and does not count as evidence until it is run with real observations and an existing photo artifact.
