# Wave 74 - Environment Doctor JSON Endpoint

Date: 2026-05-28

## Why

Packaging and beta readiness were available through `printpipe doctor --json`,
but the local app only exposed `/health` and the physical validation endpoint.
For a local command-center app, dependency, Bambu, filesystem, and signing
readiness should be readable without leaving the browser or asking another
agent to shell out.

## What changed

- Added `GET /doctor.json`.
- The endpoint returns `build_environment_report()`, the same report used by
  `printpipe doctor --json`.
- The home page service section now links to `Environment doctor JSON`.

## Boundaries

- The endpoint is read-only.
- It does not install missing dependencies.
- It does not install Apple Developer or Windows code-signing certificates.
- It does not sign, notarize, or build native installers.
- It does not install Bambu Studio on Windows.

## Verification

Focused red/green target:

```bash
.venv/bin/pytest \
  tests/test_web_server.py::test_home_response_renders_launch_controls_recent_runs_and_artifacts \
  tests/test_web_server.py::test_doctor_json_endpoint_returns_environment_report
```

The tests first failed because the home page did not link to the doctor endpoint
and `printpipe.web.server` did not expose `build_environment_report()` for the
route. They passed after the route and service link were added.
