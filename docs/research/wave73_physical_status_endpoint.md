# Wave 73 - Physical Validation JSON Endpoint

Date: 2026-05-28

## Why

Wave 72 made the physical beta gate visible in HTML. The next product layer
needs the same status as structured data so future UI, agents, and local
automation can read the gate without scraping the page or shelling out to the
CLI.

## What changed

- Added `GET /physical-status.json` to the local web app.
- The endpoint returns the same `build_physical_validation_status()` payload as
  `printpipe physical-status --json`.
- If the app is created without a runs directory, the endpoint returns `503`.

## Boundaries

- The endpoint is read-only.
- It does not write or edit `90_physical/physical_evidence.json`.
- It does not convert digital artifacts into physical proof.
- It does not mark any material family as passed without a credible passed
  evidence packet.

## Verification

Focused red/green target:

```bash
.venv/bin/pytest tests/test_web_server.py::test_physical_status_json_endpoint_returns_beta_gate_status
```

The test first failed because `/physical-status.json` returned `404`, then
passed after the route was added.
