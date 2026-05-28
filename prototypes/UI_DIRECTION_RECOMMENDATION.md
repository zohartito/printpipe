# UI Direction Recommendation

## Ranking

1. **Direction B: Model Workbench**
   - Best fit for the real app. PrintPipe's hard product problem is not just deciding pass/fail; it is understanding the generated geometry and rebuilding intent. B keeps the model/bed preview central while keeping edit controls and artifacts close enough to act.

2. **Direction A: Command Center**
   - Best for fast operational decisions. It should influence the top verdict and next-action treatment in the real route, especially when a run is blocked.

3. **Direction C: Pipeline Debugger**
   - Best for failure forensics. It should become a secondary/debug mode or a lower-page receipt section, not the default first impression.

4. **Direction D: Design Review**
   - Useful for comparing references and explaining geometry quality, but too review-oriented for the default local workbench. It is better as a future "compare parent/edit run" view.

## Direction To Ship

Ship a **B + A hybrid**: model workbench as the main body, command-center verdict as the top decision layer. This matches the current live route direction and should remain the product center.

## Exact Elements To Merge

- From A: the short "Next action" language and compact diagnostic hierarchy.
- From B: large model/bed preview, tabs, sticky edit panel, metric strip, and artifact rail near the controls.
- From C: log/timeline language for failed runs, but only below the main workbench.
- From D: reference-vs-mesh critique language later, when parent/edit comparison is real.

## Laptop And Mobile Risks

- The verdict strip can crowd at 1180px. Keep the main verdict full-width and let status cards wrap early.
- The edit sidebar can appear before the model on narrow screens. That is good for quick fixes but bad for visual review; on tablets/laptops, keep preview first.
- The model preview height should not exceed the visible laptop viewport when combined with sticky topbar and verdict.
- Artifact labels can overflow. Keep path text small, wrapping, and secondary.

## Wait For Real Rendering

- True mesh rotation, zoom, shaded STL/GLB inspection, section cuts, and support heatmaps should wait until real GLB/STL rendering exists.
- Do not fake mesh defects visually beyond honest bounds/SVG/placeholder annotations.
- Parent/edit visual diff should wait until the pipeline can produce comparable previews for both runs.

## Implementation Note

The current live `/runs/<id>` route already incorporates most of this selected direction: verdict strip, model workbench, preview tabs, edit controls, artifact links, and sticky rebuild action. The next app patch should therefore be incremental, not a rewrite: tighten copy, add a clearer next-action block when verdict is blocked/review, and improve failure/debug sections only where the current data contract already supports them.
