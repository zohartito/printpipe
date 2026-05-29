# Wave 179 - Browser Media Provider Setup

Question: after making heightfield smoke plumbing-only, can the local browser help set up a real semantic media adapter without pretending the gate is closed?

Change:

- Added `POST /media-meshgen/template`.
- Added `POST /media-meshgen/configure`.
- Added a home-page `Media meshgen setup` panel.
- Added `workspace_dir` support to the web app so browser actions can write repo-local setup files in tests and local use.

Behavior:

- `Create adapter template` writes `scripts/media_meshgen_adapter.py`.
- `Save media command` writes `.printpipe/config.json` with `media_meshgen_command`.
- The panel shows the current saved command and the required follow-up smoke command.

Proof boundary:

- Creating a template is not provider evidence.
- Saving a command is not provider evidence.
- The media meshgen gate closes only after a real semantic adapter writes a mesh and `media-meshgen-smoke` records a successful receipt.

Focused verification:

```bash
.venv/bin/pytest tests/test_web_server.py::test_home_response_renders_media_meshgen_setup_forms tests/test_web_server.py::test_post_media_meshgen_template_writes_adapter_and_redirects tests/test_web_server.py::test_post_media_meshgen_configure_writes_project_config_and_redirects -q
```

Result: 3 passed.
