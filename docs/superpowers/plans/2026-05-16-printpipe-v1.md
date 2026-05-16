# PrintPipe V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local-first Bambu reference-to-print pipeline that emits a slice-verified `.3mf` with repair, profile, and slice receipts.

**Architecture:** PrintPipe is a Python package with narrow modules for runs, input processing, mesh generation, mesh repair, geometry, Bambu profiles/bundling, slicing, reports, and CLI. The first milestone is a command-line spine; local UI and hosted cloud arrive only after the spine works.

**Tech Stack:** Python 3.11+, pytest, Bambu Studio/Bambu CLI, trimesh/pymeshlab later, Pillow/imageio/rembg later, optional mesh-generation providers.

---

## Execution Method

Use the 142-item ledger in `docs/APP_ROADMAP.md` as the source of truth. Execute in waves from `docs/AGENT_WAVES.md`, max 6 active agents per wave, with integration, tests, commits, and roadmap status updates between waves.

## Current Foundation Task

**Files:**
- Create: `README.md`
- Create: `pyproject.toml`
- Create: `src/printpipe/__init__.py`
- Create: `src/printpipe/cli.py`
- Create: `tests/test_cli.py`
- Create: `docs/ARCHITECTURE.md`
- Create: `docs/APP_ROADMAP.md`
- Create: `docs/AGENT_WAVES.md`

- [x] **Step 1: Create package skeleton**

Create a Python package with a `printpipe` console script and a minimal CLI that can show version and initialize a run root.

- [x] **Step 2: Add tests**

Add tests for `printpipe --version` and `printpipe init-run`.

- [x] **Step 3: Run foundation tests**

Run:

```bash
python -m pip install -e ".[dev]"
pytest
```

Expected: all tests pass.

- [x] **Step 4: Create private GitHub repo**

Run:

```bash
gh repo create zohartito/printpipe --private --source=. --remote=origin --push
```

Expected: remote `origin` points to the private GitHub repo and `main` is pushed.

- [x] **Step 5: Dispatch Wave 1**

Dispatch six independent agents using the package assignments in `docs/AGENT_WAVES.md`.
