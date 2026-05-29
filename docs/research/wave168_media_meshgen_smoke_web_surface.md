# Wave 168 - Media Meshgen Smoke Status Web Surface

Date: 2026-05-28

## Question

Should media meshgen smoke evidence be visible in the local browser UI, or only
through CLI/readiness JSON?

## Finding

The readiness gate now correctly depends on smoke evidence, but the browser home
page only showed the aggregate readiness card. That made the state honest but
less inspectable for prompt/image/GIF/video work, especially when a user wants to
know whether the provider itself has been smoke-tested.

## Change

- Added `/media-meshgen-smoke-status.json`.
- Added a home-page `Media meshgen smoke` panel.
- The panel shows:
  - overall smoke status
  - successful receipt count
  - latest successful run id
  - provider id
  - output path
  - message
  - next action
- Added a service link to the JSON endpoint.

## Verification

Red test:

```bash
.venv/bin/pytest tests/test_web_server.py -q -k 'media_meshgen_smoke_status or combined_readiness'
```

Result before implementation:

```text
2 failed, 1 passed
```

Focused green test:

```bash
.venv/bin/pytest tests/test_web_server.py -q -k 'media_meshgen_smoke_status or combined_readiness'
```

Result after implementation:

```text
3 passed, 58 deselected
```

Full verification:

```bash
.venv/bin/pytest -q
python -m compileall -q src
git diff --check
```

Result:

```text
586 passed, 1 skipped
compileall exit 0
diff check exit 0
```

## Boundary

This is only a visibility layer. Missing smoke evidence remains missing evidence,
and no browser panel counts as a real image/GIF/video meshgen provider.
