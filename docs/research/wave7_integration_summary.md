# Wave 7 Integration Summary

Status: complete as a local UX foundation; not a full interactive pipeline UI.

## What Landed

Wave 7 added the first stdlib-only local web surface:

- `printpipe serve` starts a local server with `--host`, `--port`, and `--runs-dir`.
- The home page renders a new-run form with file input, printer selector, filament selector, and target length field.
- The selector catalog exposes the Bambu P2S launch printer and Wave 6 material choices.
- Recent runs are read from run folders and rendered with progress state, percent complete, warning count, report link, and artifact links.
- Run artifacts can be served through safe `/runs/<run-id>/artifacts/...` download URLs.
- Static generated HTML reports can be opened through `/static/...`.
- Run reports now have clearer sections for input, mesh/repair, bed fit, slice summary, warnings, settings changes, and pre-print checklist.

## What Is Still Partial

- The local form is visible but does not yet submit into a live pipeline run.
- Progress is a snapshot from `manifest.json` and `run_report.json`, not real-time job streaming.
- Preview support exists through report/artifact links, but the home page does not yet embed image previews inline.
- `.3mf` download works when a run has a bundle artifact, but the current skeleton pipeline does not yet generate final material-specific bundles for new UI runs.

## Verification

Automated:

```text
.venv/bin/python -m pytest
149 passed, 2 skipped
```

Browser:

- Started `printpipe serve` on `127.0.0.1:8765`.
- Created a sample run from the existing STL fixture.
- Opened the home page in the in-app browser.
- Confirmed the page rendered file input, P2S selector, material selector, target length, recent run status, report link, and artifact links.
- Clicked the report link and confirmed the generated run report opened.
