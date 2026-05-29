# Wave 170 - Final Readiness Labels Media Setup Flow

Date: 2026-05-28

## Question

Does the browser final-readiness panel make the new media meshgen final action
clear enough?

## Finding

After Wave 169, `final-next` correctly started with the media provider setup
gate. The browser panel rendered the provider scaffold command, smoke command,
and follow-up check, but the primary scaffold command was unlabeled. That made a
setup/start command look like a generic command.

## Change

- Added primary command labeling in `render_final_readiness_panel()`.
- `start_command` and `setup_command` now render as `Immediate setup`.
- The media meshgen top action now reads as:
  - immediate setup: `printpipe media-meshgen-template ...`
  - run after prerequisites: `printpipe media-meshgen-smoke ...`
  - follow-up check: `printpipe media-meshgen-smoke-status ... --strict`
- Checklist rows carry the same command-kind label.

## Verification

Red test:

```bash
.venv/bin/pytest tests/test_final_readiness_web.py -q -k media_meshgen_setup_flow
```

Result before implementation:

```text
1 failed
```

Focused verification:

```bash
.venv/bin/pytest tests/test_final_readiness_web.py tests/test_web_server.py tests/test_final_plan.py -q
```

Result:

```text
93 passed
```

Full verification:

```bash
.venv/bin/pytest -q
python -m compileall -q src
git diff --check
```

Result:

```text
591 passed, 1 skipped
compileall exit 0
diff check exit 0
```

## Boundary

This is a browser rendering clarity improvement only. The media provider and
successful smoke receipt are still external/live evidence gates.
