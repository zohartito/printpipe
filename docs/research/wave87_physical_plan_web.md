# Wave 87 - Physical Action Plan in Local Web UI

## Context

Wave 86 added `printpipe physical-plan`, but the local app still only exposed the physical status gate in the browser. Zohar should be able to open PrintPipe and see the exact remaining physical validation commands without switching to terminal.

## Change

- Added `GET /physical-plan.json`.
- Added a `Physical plan JSON` link to the home-page service section.
- Added a `Physical action plan` home panel below the physical beta gate.
- The panel renders:
  - overall physical-plan status,
  - action count,
  - the proof boundary,
  - per-material missing/incomplete actions,
  - required fields,
  - exact `printpipe record-physical-evidence ...` command skeletons.

## Boundary

The UI is read-only. It does not record evidence, start prints, or convert generated coupons and slice receipts into physical proof.

## Verification

```bash
.venv/bin/pytest tests/test_web_server.py::test_physical_plan_json_endpoint_returns_action_plan tests/test_web_server.py::test_home_response_renders_physical_action_plan tests/test_web_server.py::test_home_response_renders_launch_controls_recent_runs_and_artifacts
.venv/bin/pytest tests/test_web_server.py tests/test_web_status.py tests/test_beta_physical_plan.py
```
