# Wave 161 - Run-Detail Preview Tab Anchors

Date: 2026-05-28

## Scope

Close the run-detail UI audit gap where the preview mode chips looked like tabs but were inert `<span>` elements.

## Changes

- Replaced preview chip spans with in-page anchor links.
- Added stable section IDs:
  - `model-preview`
  - `pipeline-stages`
  - `validation-results`
  - `edit-geometry`
- Routed the existing chips to useful destinations:
  - `Model` -> model preview
  - `Bed Fit` -> validation results
  - `Upper Fit` -> edit geometry
  - `Support Risk` -> validation results
  - `Slice` -> validation results
- Kept the UI server-rendered and dependency-free.

## Verification

Focused verification:

```bash
.venv/bin/pytest tests/test_web_server.py::test_run_detail_response_renders_visual_workbench_and_print_readiness -q
```

Result:

```text
1 passed
```

## Boundary

This does not add true tabbed panes, a 3D viewer, or separate Bed Fit/Slice visual modes. It makes the existing controls honest and navigable without introducing JavaScript or route changes.
