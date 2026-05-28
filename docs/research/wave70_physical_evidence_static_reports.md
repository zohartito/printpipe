# Wave 70 - Physical Evidence in Static Reports

Date: 2026-05-28

## Why

The run-detail workbench already reads `90_physical/physical_evidence.json`, but a static report bundle could still miss the physical evidence context. Beta users should be able to send the static Markdown/HTML/JSON report and have the coupon/object print evidence travel with it.

## What changed

- `build_run_report_dict()` accepts optional `physical_evidence`.
- Markdown reports render a `Physical Evidence` section.
- HTML reports render a `Physical Evidence` section.
- `printpipe record-physical-evidence` refreshes existing static reports when `80_reports/run_report.json` exists.

## Boundaries

- The command still writes the canonical packet under `90_physical/`.
- The report section mirrors recorded evidence; it does not invent physical validation.
- Runs without an existing report still get the physical packet, but no report refresh is attempted.

## Verification

Focused red/green target:

```bash
.venv/bin/pytest tests/test_reports.py::test_write_run_report_embeds_physical_evidence_in_json_and_markdown tests/test_reports_html.py::test_render_html_report_surfaces_physical_evidence_packet tests/test_beta_physical_evidence.py::test_cli_record_physical_evidence_refreshes_static_run_reports
```

The three new tests failed before implementation and passed after the report and CLI patch.
