# Wave 180 - Browser Media Meshgen Smoke

Question: once a media adapter command is saved, can the local browser run the same smoke path as the CLI?

Change:

- Added `POST /media-meshgen/smoke`.
- Added a multipart smoke form to the `Media meshgen setup` panel.
- Reused `run_media_meshgen_smoke()` so browser and CLI smoke receipts share the same contract.

Behavior:

- Requires a reference upload named `reference`.
- Accepts an optional prompt hint.
- Resolves the current `.printpipe/config.json` media command from the web app workspace.
- Writes normal `20_meshgen/smoke.json` receipts under the configured runs directory.

Proof boundary:

- A smoke receipt proves the adapter executed and wrote a mesh.
- Wave 178 still applies: the built-in heightfield adapter is plumbing-only and does not prove semantic reconstruction.
- Readiness gates remain responsible for deciding whether the evidence satisfies the product gate.

Focused verification:

```bash
.venv/bin/pytest tests/test_web_server.py::test_post_media_meshgen_smoke_runs_configured_adapter_and_redirects tests/test_web_server.py::test_post_media_meshgen_smoke_requires_reference tests/test_web_server.py::test_home_response_renders_media_meshgen_setup_forms -q
```

Result: 3 passed.
