# Wave 149 - Trusted-User Action Plan UI Parity

## Question

Does the dedicated trusted-user action-plan panel show the same review context and supporting files that final-readiness can show?

## Finding

After Wave 148, `beta-feedback-plan` actions carried structured handoff context and `final-plan`/final-readiness rendered it through the shared final action flow.

The home page also has a dedicated `Trusted-user action plan` panel, but its action cards still rendered mostly the generated `record-beta-feedback` command. That meant the raw JSON and final-readiness were informative, while the specialized beta-review panel hid the review target, handoff sheet, report, and bundle paths.

## Change

- Render `Review context` on trusted-user action cards.
- Include material, printer, input type, tester, and run folder.
- Render handoff Markdown, run report, and bundle paths when present.
- Split the immediate review handoff command from the later `Record after review` command.

## Verification

```bash
.venv/bin/pytest \
  tests/test_web_server.py::test_home_response_renders_trusted_user_action_context_and_files \
  tests/test_web_server.py::test_home_response_renders_trusted_user_feedback_action_plan -q
```

Result: `2 passed`.

## Boundary

This is UI parity only. It still does not create trusted-user evidence or satisfy the beta gate. Only completed feedback packets from real trusted users count.
