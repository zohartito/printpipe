# Wave 160 - UI Evidence Honesty

Date: 2026-05-28

## Scope

Close the next small audit gaps where UI/report surfaces could imply evidence was stronger than the files on disk:

- recent-run cards showed pipeline status and bundle downloads without a local print verdict
- trusted-user outcomes were labeled recorded even when all outcome counters were zero
- static HTML reports linked to artifact files even when the files were missing

## Changes

- Recent-run cards now render a `Print decision` block before artifact groups when a `.3mf` bundle exists.
- That block reuses `build_run_detail()` and the same `print_verdict` contract used by the run-detail workbench.
- Trusted-user feedback outcomes now filter zero counters and use `missing` plus `No completed tester outcomes recorded.` when no completed outcomes exist.
- Static HTML reports check artifact paths when a run layout is available. Existing files remain linked; missing files render as `Artifact file missing` with no `href`.

## Verification

Focused verification:

```bash
.venv/bin/pytest tests/test_web_server.py tests/test_reports_html.py -q
```

Result:

```text
67 passed
```

## Boundary

This wave does not create physical print proof, trusted-user feedback, successful slice receipts, or signed release artifacts. It only makes the local UI and static report less likely to overclaim.
