# Wave 115 - Physical Print Handoff Sheets

## Purpose

Wave 114 generated printable validation coupon artifacts, but a human still had to connect the coupon STL, the material-specific inspection checklist, the proof boundary, and the final evidence-recording command. Wave 115 makes each starter folder self-contained for print day by writing a Markdown handoff sheet next to the not-yet-printed evidence packet.

## What changed

- `printpipe physical-start --family <family> --runs-dir runs --operator Zohar --json` now writes `90_physical/physical_print_handoff.md`.
- The JSON payload now includes `handoff_markdown_path`.
- The human CLI output now prints:
  - `coupon stl: ...`
  - `print handoff: ...`
- `physical-plan` now surfaces the handoff path in both text and JSON output.
- The final-readiness web panel now shows the handoff path beside the coupon path.

## Handoff sheet contents

Each handoff sheet includes:

- material family
- material label
- object label
- run folder
- coupon STL path
- coupon JSON sidecar path
- material-specific validation checks
- exact `record-physical-evidence` command to run after the print
- proof boundary that digital artifacts do not count as physical proof

## Local evidence generated

Ignored local starter folders now contain:

- `runs/physical-pla-validation/90_physical/physical_print_handoff.md`
- `runs/physical-petg-validation/90_physical/physical_print_handoff.md`
- `runs/physical-tpu-validation/90_physical/physical_print_handoff.md`

## Verification

- `pytest tests/test_beta_physical_plan.py::test_start_physical_validation_writes_not_printed_starter_packet -q`
- `pytest tests/test_beta_physical_plan.py::test_physical_validation_plan_surfaces_started_coupon_artifacts -q`
- `pytest tests/test_beta_physical_plan.py::test_cli_physical_start_text_prints_coupon_and_handoff_paths -q`
- `pytest tests/test_final_readiness_web.py -q`
- `printpipe physical-start --family pla --runs-dir runs --operator Zohar --json`
- `printpipe physical-start --family petg --runs-dir runs --operator Zohar --json`
- `printpipe physical-start --family tpu --runs-dir runs --operator Zohar --json`
- `printpipe physical-plan --runs-dir runs`
- `printpipe final-plan --release-dir dist/release --runs-dir runs --regression-manifest regressions/dogfood_failures.json --json`

## Boundary

The handoff sheet is not evidence. It is a print-day instruction sheet. The physical validation gate remains open until real PLA, PETG, and TPU prints are recorded with credible observations and photo artifacts.
