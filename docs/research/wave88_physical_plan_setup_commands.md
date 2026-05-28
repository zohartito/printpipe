# Wave 88 - Runnable Physical Plan Setup Commands

## Context

`printpipe physical-plan` exposed exact evidence-recording commands, but missing material families still used abstract `<run-root-for-...>` placeholders. That made the plan honest but less runnable on print day, because `record-physical-evidence` requires the target run folder to exist.

## Change

- Missing material-family actions now target deterministic run folders:
  - `runs/physical-pla-validation`
  - `runs/physical-petg-validation`
  - `runs/physical-tpu-validation`
- Each missing family action includes `setup_command`.
- The rendered CLI plan prints `setup: mkdir -p ".../runs/physical-<family>-validation"` before the evidence command.
- The web action-plan cards render the same setup command before the `record-physical-evidence` command.
- Incomplete existing evidence packets still point at the existing packet run folder and do not emit setup commands.

## Boundary

These commands only prepare the evidence folder and capture later observations. Zohar still needs to physically print the PLA, PETG, and TPU coupon/small-object samples, take photos, replace placeholder photo paths, and record real observations before F9 can pass.

## Verification

```bash
.venv/bin/pytest tests/test_beta_physical_plan.py tests/test_web_server.py::test_home_response_renders_physical_action_plan tests/test_web_server.py::test_physical_plan_json_endpoint_returns_action_plan
.venv/bin/printpipe physical-plan --runs-dir runs
```
