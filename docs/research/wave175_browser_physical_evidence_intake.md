# Wave 175 - Browser Physical Evidence Intake

Date: 2026-05-29

## Question

Can the local browser record real post-print physical evidence after a starter
packet exists, without letting the UI fabricate a pass?

## Finding

Wave 174 let the browser create a not-yet-printed physical validation starter
packet. The next gap was evidence intake: after Zohar prints a coupon, the app
still required copying the generated CLI command. That made the local browser a
planning surface, not a full physical-validation workflow.

## Change

- Added `POST /physical/record`.
- Added a browser evidence form to already-started PLA/PETG/TPU physical
  validation action cards.
- The record route looks up the current physical action by family instead of
  trusting an arbitrary run path from the form.
- The route rejects missing starter packets.
- The route requires a photo upload before writing printed evidence.
- Uploaded photos are copied into `90_physical/artifacts/`.
- Evidence JSON/Markdown is written through the same physical evidence writer
  used by `printpipe record-physical-evidence`.

## Verification

Red tests:

```bash
.venv/bin/pytest tests/test_web_server.py::test_home_response_renders_physical_record_form_after_starter_packet tests/test_web_server.py::test_post_physical_record_writes_passed_evidence_and_copies_photo tests/test_web_server.py::test_post_physical_record_requires_photo -q
```

Result before implementation:

```text
3 failed
```

Focused green:

```bash
.venv/bin/pytest tests/test_web_server.py::test_home_response_renders_physical_record_form_after_starter_packet tests/test_web_server.py::test_post_physical_record_writes_passed_evidence_and_copies_photo tests/test_web_server.py::test_post_physical_record_requires_photo -q
```

Result:

```text
3 passed
```

Web suite:

```bash
.venv/bin/pytest tests/test_web_server.py -q
```

Result:

```text
66 passed
```

Full verification:

```bash
.venv/bin/pytest -q
python -m compileall -q src
git diff --check
```

Result:

```text
610 passed, 1 skipped
compileall exit 0
diff check exit 0
```

## Boundary

The browser route requires a photo file, but the software still cannot know
whether the photo represents a truthful physical print. It records evidence; it
does not create real-world proof by itself.
