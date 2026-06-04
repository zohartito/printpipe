# PrintPipe Agentic Workflow Playbook

This document captures the repeatable way we ran PrintPipe: the agent stack,
the proof rules, the failure lessons, and the GitHub habits that made the work
usable instead of just busy. It is meant to be copied into future projects where
Zohar wants Codex, Cursor, Claude Code, or other agents to collaborate without
losing the plot.

## Why This Lives Here

PrintPipe was not only a 3D-printing pipeline. It became a working pattern for
turning a vague product idea into a tested local app with receipts:

- Start with the real user goal, not a fake minimal demo.
- Convert the goal into a numbered roadmap.
- Work in waves.
- Let multiple agents explore independent questions.
- Require evidence before calling anything done.
- Keep failures visible.
- Push the work to GitHub so the next agent can inherit the truth.

The durable lesson: plans, prompts, receipts, and retrospectives are product
assets. They belong in the repo next to the code.

## Core Operating Rules

1. Preserve the current repo state.
2. Never delete or revert unrelated user changes.
3. Add narrow artifacts instead of rewriting history.
4. Use tests and receipts before claims.
5. Treat generated plans as guidance, not proof.
6. Separate software readiness from real-world readiness.
7. Push useful decisions and failures to GitHub.
8. Keep local/private machine state out of commits.

## The Wave Model

The useful unit of work was a wave:

1. Pick one specific frontier.
2. Define what proof would close it.
3. Add tests or a failing reproducer first when changing behavior.
4. Implement the smallest real improvement.
5. Run focused verification.
6. Run broad verification when the blast radius touches shared code.
7. Document what changed and what it does not prove.
8. Commit with a clear message.
9. Push to GitHub.

The wave log in `docs/AGENT_WAVES.md` became the project memory. It helped us
avoid re-litigating the same questions and made handoffs to Cursor/Claude more
grounded.

## Agent Stack

Use agents by role, not by vibes.

| Role | Best Use | Output |
| --- | --- | --- |
| Codex main agent | Implementation, tests, repo orchestration, GitHub pushes | Code, docs, commits |
| Research subagent | Market/tool/provider research, docs, source-backed comparisons | Findings with recommendations |
| Cursor | UI/UX variants, component critique, focused frontend patches | Prototype HTML, UI notes, narrow server/UI changes |
| Claude/Opus | Independent audit, adversarial review, second opinion | Severity-ranked findings and prompts |
| Human/Zohar | Physical printer actions, fit judgment, product taste, final calls | Real-world evidence and direction |

The best pattern was not "142 agents blindly." It was:

- Parallelize independent research or audit tasks.
- Keep implementation in one branch unless the task is truly separable.
- Merge ideas back into a single roadmap.
- Verify agent claims directly before trusting them.

## Sequential Stack For Future Projects

1. Capture the messy original goal.
2. Read prior conversation or handoff files.
3. Write a brutal audit: worked, did not work, why.
4. Make a numbered roadmap.
5. Split roadmap into phases.
6. Identify proof gates for each phase.
7. Create repo and run-folder/receipt conventions.
8. Build the smallest end-to-end spine.
9. Add real input/output fixtures.
10. Add failure receipts.
11. Add reports.
12. Add local UI.
13. Add edit/rebuild loops.
14. Add physical or real-world validation packets.
15. Add beta feedback packets.
16. Add release/distribution packets.
17. Keep a final-next command or endpoint for the next action.
18. Keep all docs honest about what is not proven.

## Proof Boundaries

This project repeatedly improved when we separated setup from proof.

| Claim | Proof Required |
| --- | --- |
| Mesh path works | A run receipt with generated/repaired/oriented mesh artifacts |
| Bambu bundle works | Valid `.3mf` contents plus Bambu-compatible metadata |
| Slice works | Slice receipt with parsed time/mass/layers/cost |
| Media provider works | Successful `media-meshgen-smoke` receipt pointing at an output mesh |
| ComfyUI workflow is ready | Static inspector plus runtime preflight, then smoke receipt |
| TPU settings work | Real printed coupon or object with physical evidence |
| Slipper works | Printed slipper, fit check, photos, flex/wear notes |
| Beta works | Completed trusted-user feedback packets |
| Release works | Signed/notarized/verified artifacts, not just package files |

The phrase "not evidence" is important. It prevented generated docs, starter
packets, fake examples, or placeholder commands from being mistaken for proof.

## What Worked

- Numbered phases kept the huge project navigable.
- `final-next` made the next action machine-readable.
- Receipts made failure states visible instead of mysterious.
- Browser/UI work improved when Cursor first made throwaway prototypes.
- Audits from another model found bugs the main agent missed.
- Test-first patches were faster than guessing.
- Committing after verified waves made the work recoverable.
- Local-first architecture avoided premature cloud complexity.
- Explicit "this does not prove X" copy reduced false confidence.

## What Did Not Work

- Treating generated mesh as printable before topology repair.
- Assuming Bambu Studio CLI and GUI use identical placement behavior.
- Assuming slicer warnings were harmless.
- Using invalid Bambu enum values such as unsupported support styles.
- Treating visible settings as the only settings that mattered.
- Letting physical proof be implied by digital artifacts.
- Letting trusted-user handoffs look like completed feedback.
- Using shell-only configuration for provider commands.
- Asking the user for approval when the active sandbox context had gone stale.

## Trial-And-Error Lessons

### Mesh Generation

Higher-resolution generation did not automatically mean better printable detail.
For the slipper, a multi-view mesh preserved important sole texture better than
a smoother higher-octree output. Future pipelines should compare outputs using
print intent, not just face count.

### Mesh Repair

The non-manifold slipper failure was the real blocker, not a cosmetic issue.
Repair and topology validation need to be first-class stages with JSON receipts.
Do not send generated meshes directly to Bambu Studio and hope.

### Bambu `.3mf`

Bambu Studio checks metadata. A bundle can contain geometry and still be treated
as foreign unless the project metadata looks Bambu-native. Signature/metadata
details belong in tests.

### Bambu CLI

Bambu Studio 2.6 on macOS 26.5 crashed on some raw/direct STL slice paths. The
supported path became fully resolved Bambu-native `.3mf` bundles. Raw CLI crash
cases should be documented, not hidden.

### Supports

The slipper had a floating cantilever. "No supports" was an assumption, not a
fact. Slicer warnings must feed back into support strategy.

### TPU

Digital TPU settings are not physical validation. A flex coupon comes before a
long wearable print.

### Physical Evidence

Starter packets, handoff sheets, and record commands are useful but not proof.
Proof needs a real print, real photo/artifact, observations, and explicit
outcome fields.

### Permissions

The Codex permission context can go stale. When sandboxing unexpectedly asks for
approval or blocks repo writes, first check the active permission state. Use a
dummy prompt or re-apply full access in the chat permissions menu before
assuming the project is broken.

## Useful Commands

```bash
# Current immediate endgame action
printpipe final-next --release-dir dist/release --runs-dir runs --json

# Full readiness plan
printpipe final-plan --release-dir dist/release --runs-dir runs

# Environment and dependency checks
printpipe doctor --json
printpipe readiness --runs-dir runs --strict

# Media provider setup
printpipe media-meshgen-template --preset comfyui-api --output scripts/media_meshgen_adapter.py
printpipe media-meshgen-comfyui-inspect workflows/image_to_glb.json --json
printpipe media-meshgen-comfyui-preflight --json --strict
printpipe media-meshgen-smoke reference.png --runs-dir runs --output-format glb
printpipe media-meshgen-smoke-status --runs-dir runs --strict

# Physical evidence
printpipe physical-plan --runs-dir runs
printpipe physical-start --runs-dir runs --family tpu --slice
printpipe record-physical-evidence <run-root> --print-status "<passed|failed|partial>" --photo /path/to/photo.jpg

# Beta evidence
printpipe beta-feedback-plan --runs-dir runs
printpipe record-beta-feedback <run-root> --tester "Name" --outcome "<passed|failed|partial|not_run>"

# Release evidence
printpipe release-plan --release-dir dist/release --runs-dir runs
printpipe release-start --release-dir dist/release --runs-dir runs
printpipe release-status --release-dir dist/release --runs-dir runs --strict
```

## Verification Stack

Run the narrowest relevant test first, then broaden.

```bash
.venv/bin/pytest tests/test_final_plan.py -q
.venv/bin/pytest tests/test_web_server.py -q
.venv/bin/pytest -q
PYTHONPYCACHEPREFIX=/private/tmp/printpipe_pycache python -m compileall -q src
git diff --check
```

When the sandbox blocks `__pycache__` writes, redirect `PYTHONPYCACHEPREFIX` to
`/private/tmp` rather than asking Zohar for approval again.

## GitHub Habit

Every meaningful wave should end with:

```bash
git status --short --branch
git diff --check
git add <intentional files>
git commit -m "<plain English wave result>"
git push
```

Do not stage unrelated files. In this repo, leave untracked handoff drafts alone
unless Zohar asks to include them.

## Handoff Prompt Template

Use this when handing the project to another agent:

```text
You are taking over PrintPipe. Work from the current git checkout and current
roadmap, not from memory. Read README.md, docs/APP_ROADMAP.md,
docs/AGENT_WAVES.md, and docs/AGENTIC_WORKFLOW_PLAYBOOK.md first.

Rules:
- Preserve unrelated user changes.
- Do not call generated handoffs "proof."
- Add tests before behavior changes.
- Run focused tests, full tests when shared code changes, compileall, and
  git diff --check before claims.
- Commit and push only intentional files.

Current frontier:
- Check `printpipe final-next --release-dir dist/release --runs-dir runs --json`.
- The remaining true gates are semantic media meshgen smoke, physical prints,
  trusted-user feedback, and signed release evidence.
```

## When To Make A New Repo

Use the existing repo when the workflow is tied to PrintPipe's architecture,
receipts, or product lessons.

Make a new repo only when the artifact is generic across many projects, such as:

- a reusable agent-orchestration template,
- a generic "AI project evidence gates" starter,
- a cross-project Codex/Cursor/Claude workflow kit,
- a standalone dashboard for agent waves and final-next style planning.

For now, this document belongs in PrintPipe because it explains exactly how this
project reached its current state.
