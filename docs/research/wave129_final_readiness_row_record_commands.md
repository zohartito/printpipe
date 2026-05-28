# Wave 129 - Final Readiness Row Record Commands

## Purpose

Wave 128 made the top final-next panel carry the post-print evidence command. The remaining web gap was the checklist row view: PLA, PETG, and TPU rows could show the immediate handoff/open-folder command but not their own post-print `record-physical-evidence` command.

## What changed

- Final-readiness action rows now preserve `record_command` when the immediate command is a print-handoff action.
- Starter/setup rows still hide record commands so the UI does not invite recording evidence before a starter packet exists.
- The web checklist renders row-level `Record after print` command blocks.

## Boundary

These are execution instructions only. The physical validation gate still requires a real printed coupon, real observations, and an existing photo artifact.
