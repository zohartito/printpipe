# Wave 89 - Physical Validation Starter Packets

## Context

Wave 88 made the physical validation plan runnable by adding deterministic setup folders and exact `record-physical-evidence` commands. The remaining friction was that Zohar still had to manually create the initial evidence packet target before print day, while PrintPipe needed to keep the proof boundary honest.

## Change

- Added `printpipe physical-start --family pla|petg|tpu --runs-dir runs --operator ...`.
- Added `printpipe.beta.physical_start.start_physical_validation()` for code and tests.
- Missing-family physical-plan actions now include a `start_command` between setup and record.
- The local web physical action cards render the same `physical-start` command.
- The starter command writes `90_physical/physical_evidence.json` and `.md` in the deterministic validation run folder.
- Starter evidence uses `print_status=not_printed` and notes that it is not passed evidence.

## Boundary

Starter packets are a convenience for print-day setup, not proof. `printpipe physical-status --strict` still fails until the real PLA, PETG, and TPU prints are recorded with credible passed status, observations, and photos.

## Verification

```bash
.venv/bin/pytest tests/test_beta_physical_plan.py tests/test_web_server.py::test_home_response_renders_physical_action_plan
.venv/bin/printpipe physical-start --family tpu --runs-dir "$TMPDIR/printpipe-runs" --operator Zohar --json
.venv/bin/printpipe physical-status --runs-dir "$TMPDIR/printpipe-runs" --json --strict
```
