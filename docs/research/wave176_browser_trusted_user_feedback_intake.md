# Wave 176 - Browser Trusted-User Feedback Intake

Date: 2026-05-29

## Question

Can the local browser record trusted-user beta feedback from an existing review
handoff without trusting arbitrary run paths or fabricating tester evidence?

## Finding

The CLI already supported `record-beta-feedback`, and the home page already
showed trusted-user action-plan cards. The missing piece was browser intake:
after a handoff existed, the user still had to copy a CLI command to turn the
review into a structured feedback packet.

## Change

- Added `POST /beta-feedback/record`.
- Added a multipart feedback form to trusted-user action cards when a real
  handoff-backed run exists.
- The route resolves the target action by current feedback-plan slot.
- Run folder, tester, input type, material, and printer come from the action
  plan/handoff, not from arbitrary form fields.
- Blank summaries are rejected before packet creation.
- Optional uploaded review artifacts are copied into `90_beta/artifacts/`.
- Feedback JSON/Markdown is written through the same feedback writer as
  `printpipe record-beta-feedback`.

## Verification

Red tests:

```bash
.venv/bin/pytest tests/test_web_server.py::test_home_response_renders_trusted_user_record_form_after_handoff tests/test_web_server.py::test_post_beta_feedback_record_writes_packet_and_copies_artifact tests/test_web_server.py::test_post_beta_feedback_record_requires_summary -q
```

Result before implementation:

```text
3 failed
```

Focused green:

```bash
.venv/bin/pytest tests/test_web_server.py::test_home_response_renders_trusted_user_record_form_after_handoff tests/test_web_server.py::test_post_beta_feedback_record_writes_packet_and_copies_artifact tests/test_web_server.py::test_post_beta_feedback_record_requires_summary -q
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
69 passed
```

Full verification:

```bash
.venv/bin/pytest -q
python -m compileall -q src
git diff --check
```

Result:

```text
613 passed, 1 skipped
compileall exit 0
diff check exit 0
```

## Boundary

This makes browser-side intake real, but the beta gate still requires three
real trusted users to submit completed feedback. The form cannot prove the
tester exists or that the review was truthful.
