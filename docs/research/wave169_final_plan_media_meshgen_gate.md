# Wave 169 - Final Plan Includes Media Meshgen Provider Gate

Date: 2026-05-28

## Question

Should `final-plan` only track physical, trusted-user, and release gates, or
should it also track the still-open image/GIF/video media meshgen provider gate?

## Finding

After Waves 166-168, readiness and the home page correctly showed the missing
media meshgen provider/smoke evidence. `final-plan` and `final-next` still
started at physical validation, so the main endgame checklist could skip the
non-mesh input gap even though image/GIF/video is part of the product promise.

## Change

- Added `build_media_meshgen_action_plan()`.
- Added a `media_meshgen_provider` section to `build_final_action_plan()`.
- If no provider is configured, `final-next` starts with
  `printpipe media-meshgen-template`.
- If a provider is configured but no smoke evidence exists, `final-next` points
  at `printpipe media-meshgen-smoke`.
- If a provider and successful smoke receipt both exist, the section is ready.
- Updated the final-plan proof boundary so media smoke receipts are named
  alongside physical packets, trusted-user feedback, and signed artifacts.

## Verification

Focused final-plan tests:

```bash
.venv/bin/pytest tests/test_final_plan.py -q
```

Result:

```text
22 passed
```

Focused web/final-readiness/readiness tests:

```bash
.venv/bin/pytest \
  tests/test_web_server.py \
  tests/test_final_readiness_web.py \
  tests/test_cli_readiness.py \
  -q
```

Result:

```text
75 passed
```

Manual command check:

```bash
.venv/bin/printpipe final-next --runs-dir runs --release-dir dist/release --json
```

Result excerpt:

```text
action_count: 10
next_action.section_id: media_meshgen_provider
next_action.action_id: configure_media_meshgen_provider
next_command: printpipe media-meshgen-template --output scripts/media_meshgen_adapter.py
```

Full verification:

```bash
.venv/bin/pytest -q
python -m compileall -q src
git diff --check
```

Result:

```text
590 passed, 1 skipped
compileall exit 0
diff check exit 0
```

## Boundary

This does not install or validate a live provider. It makes the final endgame
plan honest about the provider/smoke evidence still missing for image/GIF/video
inputs.
