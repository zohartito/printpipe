# Wave 76 - Readiness Gates on Home Page

Date: 2026-05-28

## Why

Wave 75 added a combined readiness report and JSON endpoint, but a user opening
the local app still had to click into JSON to see the complete gate list. The
home page should answer the practical question immediately: what blocks beta or
release readiness right now?

## What changed

- Added a `Readiness gates` panel to the home page.
- The panel shows the overall readiness status and action-required count.
- The panel renders each gate with status, detail, and action.
- The panel uses `build_beta_readiness_report()` so it stays aligned with
  `/readiness.json`.

## Boundaries

- This is a display layer.
- It does not record physical evidence.
- It does not install missing dependencies or certificates.
- It does not sign, notarize, or build release artifacts.

## Verification

Focused red/green target:

```bash
.venv/bin/pytest tests/test_web_server.py::test_home_response_renders_combined_readiness_summary
```

The test first failed because the home page did not include `Readiness gates`.
It passed after the panel was rendered from the combined readiness report.
