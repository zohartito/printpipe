# printpipe — LEARNINGS (flywheel)

Durable, machine-appended lessons from this repo's loops. The watch-folder loop
(`tools/watch_3mf_queue.py`) appends one line per run with new files. Read
before non-trivial work; consolidate with the `dream` skill as it grows.

## Loops in this repo
- **EVENT watch-folder (added, loop map #29):** `tools/watch_3mf_queue.py` —
  new `.3mf` in the inbox → `validate_bundle` → slice via
  `run_bambu_cli_slice_stage` (behind the existing Bambu CLI gate) → queue
  report JSON (schema `printpipe.watch_queue.v1`). Idempotent (content-hash
  state) + `--max-files` cap. Triggered by `com.zohar.printpipe-watch.plist`
  (`WatchPaths` on the inbox).

## Seed lessons
- The slice gate is `PRINTPIPE_BAMBU_STUDIO_CLI` (fallbacks `BAMBU_STUDIO_CLI`,
  `BAMBU_STUDIO_EXECUTABLE`). Without a discoverable CLI, slicing SKIPS honestly
  — never fabricate a slice receipt (AGENTS.md danger zone). The watch loop
  reports `skipped_gate_closed` in that case, still validating every file.
- `validate_bundle` requires the Bambu archive members + an `Application`
  metadata starting with the Bambu prefix; a plain zip or non-Bambu 3MF fails
  validation and is not sliced.
- `runs/` is gitignored — inbox, state (`.watch-state.json`), and the queue
  report live there and are never committed.

## Run log (auto-appended below)
- 2026-08-12T15:56:38+00:00 [printpipe-watch-3mf] new=2 valid=1 invalid=1 gate_open=True sliced_ok=0 sliced_skipped=0
