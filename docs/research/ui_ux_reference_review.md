# UI/UX Reference Review

## Current UI Critique

The current stdlib-rendered web UI already has the right product spine: a run-detail route, a print-readiness verdict, validation checks, a large workbench area, edit/rebuild controls, artifact discovery, and pipeline state. It also preserves the important local-first constraints: no frontend framework, no remote dependencies, safe artifact URLs, and a stable `build_run_detail()` contract.

What still feels too flat is priority. The page contains the right information, but the next action can blur with evidence panels. A failed or risky run should answer, in order: can I print this, why not, what do I change, and what artifact can I trust? The model preview is present, but it should behave more like the center of the page than a report illustration. Pipeline and artifacts should support the decision rather than compete with it.

The next user action on a run detail page should be one explicit primary action: rebuild from a saved geometry edit recipe when validation is not print-ready, or open/download the 3MF when all gates pass. Secondary actions should be inspect slice receipt, inspect artifacts, and compare parent/edit run evidence.

## Reference Patterns

### ReUI / shadcn-style component catalogs
- Borrow: dense dashboard primitives, data-grid discipline, copy-and-own component thinking, command/card/table consistency.
- Do not borrow: React/Tailwind dependency assumptions or component-catalog visual sameness.
- PrintPipe mapping: use the disciplined primitives in plain CSS: verdict cards, artifact tables, compact status chips, and predictable form controls.

### 21st.dev / Agent Elements
- Borrow: tool-card consistency, visible pending/error states, action rows that make tool execution understandable.
- Do not borrow: chat-first layouts or agent conversation chrome.
- PrintPipe mapping: each pipeline stage can act like a tool card: status, message, artifact, and retry/edit affordance.

### Linear
- Borrow: minimal issue-detail hierarchy: title/status on top, main content for the work, side panel for properties/actions.
- Do not borrow: too much project-management vocabulary.
- PrintPipe mapping: run detail should feel like an issue page for a print job: verdict/status, current object, properties, and activity/pipeline below.

### Vercel Deployments
- Borrow: deployment summary plus logs/resources, clear failed/warning coloring, direct access to produced artifacts.
- Do not borrow: cloud/team/deployment concepts that do not fit a local app.
- PrintPipe mapping: a run is a deployment-like artifact build: verdict, generated package, logs, build/slice receipts, and resource outputs.

### Sentry Issue Details
- Borrow: event highlights, suspect-cause framing, breadcrumbs/logs for debugging.
- Do not borrow: incident-management density as the default view.
- PrintPipe mapping: failed mesh/slice runs should show the suspected blocker at the top: non-manifold repair, bed fit, support/cantilever, or slice crash.

### Replicate Predictions
- Borrow: input/output/logs/status object model and side-by-side input controls with output result.
- Do not borrow: cloud sharing/account affordances.
- PrintPipe mapping: the workbench should show input intent and edit recipe beside the generated output, with logs and artifacts below.

### Figma Dev Mode
- Borrow: inspect-mode framing, canvas-first layout, right-side properties panel, annotations and measurements.
- Do not borrow: design-handoff code snippets.
- PrintPipe mapping: model preview should gain measurements, bed bounds, risk annotations, and selected-artifact properties.

### Runway
- Borrow: creative iteration loop: references, settings, generated output, reuse-as-input, and regenerate.
- Do not borrow: buried tools or inconsistent tool surfaces.
- PrintPipe mapping: run detail should support iterative rebuilds while keeping the original run immutable.

### Raycast
- Borrow: primary/secondary action clarity, keyboard-minded action naming, fast focused screens.
- Do not borrow: command palette as the main UI.
- PrintPipe mapping: every run page needs one obvious primary action and a small set of clean secondary actions.

### ComfyUI
- Borrow: queue/history/debugging mental model and clear execution stages.
- Do not borrow: node graph complexity.
- PrintPipe mapping: show pipeline stages as an execution receipt and support parent/edit run history later.

### Blender / Rhino
- Borrow: viewport plus properties panel plus asset/outliner regions; task-specific workspaces.
- Do not borrow: full CAD panel density.
- PrintPipe mapping: keep a real model/bed viewport central, with edit properties on the right and artifacts as the asset rail.

## Recommended Design Direction

Use a restrained production workbench. The best base is a command-center/workbench hybrid: verdict strip first, large model/bed preview second, sticky edit/rebuild panel to the right, artifacts close to the edit controls, and pipeline/warnings below as receipts. Avoid hero language, nested cards, chat metaphors, and decorative 3D illusions that imply more real geometry inspection than PrintPipe currently provides.

Until real GLB/STL rendering is available, the preview should be honest: render deterministic SVG/bounds previews when available and use a neutral placeholder otherwise. The UI can still provide measurements, bed fit, and support-risk labels, but it should not pretend to show a full mesh viewer.
