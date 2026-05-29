# Wave 174 - Browser Physical Starter Action

Date: 2026-05-29

## Question

Can the local browser UI help Zohar start the next honest physical-validation
gate without copying a CLI command, while still avoiding fake physical proof?

## Finding

After media meshgen readiness moved to `ready`, `final-next` correctly pointed at
physical validation. The browser showed the physical action plan and exact CLI
commands, but it could not create the starter packet itself. That left the local
app less useful than the terminal for the next real-world gate.

## Change

- Added a local `POST /physical/start` route.
- Added a `Create starter packet` form to missing PLA/PETG/TPU physical action
  cards.
- The route calls the same `start_physical_validation()` path as the CLI.
- The generated packet remains `not_printed`; it creates printable artifacts and
  handoff files, not passed evidence.
- The route redirects to `/#physical-action-plan` so the refreshed home page
  shows generated coupon/bundle/handoff paths and the post-print record command.

## Verification

Red tests:

```bash
.venv/bin/pytest tests/test_web_server.py::test_home_response_renders_physical_start_form tests/test_web_server.py::test_post_physical_start_creates_starter_packet_and_redirects -q
```

Result before implementation:

```text
2 failed
```

Focused green:

```bash
.venv/bin/pytest tests/test_web_server.py::test_home_response_renders_physical_start_form tests/test_web_server.py::test_post_physical_start_creates_starter_packet_and_redirects -q
```

Result:

```text
2 passed
```

Web suite:

```bash
.venv/bin/pytest tests/test_web_server.py -q
```

Result:

```text
63 passed
```

Full verification:

```bash
.venv/bin/pytest -q
python -m compileall -q src
git diff --check
```

Result:

```text
607 passed, 1 skipped
compileall exit 0
diff check exit 0
```

## Boundary

This is a starter/handoff action only. It does not claim a print occurred, does
not attach photos, and does not close PLA/PETG/TPU physical validation.
