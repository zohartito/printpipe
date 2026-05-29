# Wave 177 - Browser Release Handoff Start

Question: can the local browser start the same release-distribution handoff that the CLI already supports, without pretending signed release evidence exists?

Finding: before this wave, the home page rendered the release distribution action plan and CLI `release-start` command, but the browser could not create the handoff directly.

Change:

- Added `POST /release/start`.
- Added a `Create release handoff` form to the release distribution panel when the current plan has a release start command.
- Kept the route wired to `start_release_distribution_handoff()` so browser and CLI use the same writer.
- Redirected back to `/#release-distribution-plan`.

Proof boundary:

- The route writes only `release_distribution_handoff.md`.
- It does not create `release_manifest.json`.
- It does not sign, notarize, build installers, or satisfy Developer ID / Windows signing gates.

Verification:

```bash
.venv/bin/pytest tests/test_web_server.py::test_home_response_renders_release_start_form tests/test_web_server.py::test_post_release_start_writes_handoff_and_redirects -q
```

Result: 2 passed.
