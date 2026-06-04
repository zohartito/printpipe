Wave 194 - Agentic Workflow Capture

Question: where should the reusable Codex/Cursor/Claude workflow lessons live so future projects can inherit them?

Decision: keep them in the existing PrintPipe repo, under `docs/`, instead of starting a new repository right now.

Why:
- The workflow lessons are tightly coupled to PrintPipe's receipts, gates, wave log, and final-next model.
- Adding docs does not change app behavior.
- A future generic agent-workflow repo can still be extracted later.

Added:
- `docs/AGENTIC_WORKFLOW_PLAYBOOK.md`

Captured:
- wave-by-wave operating model
- agent roles for Codex, Cursor, Claude/Opus, research agents, and Zohar
- proof boundaries separating setup from evidence
- lessons from mesh repair, Bambu 3MF, Bambu CLI, TPU, physical proof, and stale permission contexts
- verification and GitHub habits
- handoff prompt template for future agents

Boundary:
- This is documentation only.
- It does not change PrintPipe behavior.
- It does not close media, physical, trusted-user, or release gates.
