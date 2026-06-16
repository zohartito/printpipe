# Phase 1 — general parametric code-gen engine (scope)

> Scope this with the user before firing the agents. Same two-lane pattern as Phase 0 (Codex owns the
> systems/geometry math behind a contract; Claude builds the integration to that contract). Phase 0
> (the `FabricationReport` verification engine) is landed and green — Phase 1 makes **generation**
> general while keeping that verification moat.

## Goal
Evolve PrintPipe from the **fixed** `EnclosureSpec` / `parametric_cad` primitives (box / enclosure /
lid / grip) to a **general** engine where the agent **authors `build123d` parametric code**, executed
in a sandbox → rendered → validated (Phase 0) → auto-fixed. This is the "LLMs write code, a kernel
executes it" engine from `PRINTPIPE_AGENT_BRIEF.md` §1 — so PrintPipe can design *arbitrary* parts by
conversation, not only the hard-coded primitives.

## Why now
- Phase 0 gave us the **verification** layer (the moat). Phase 1 makes **generation** general so the
  product isn't capped at the enclosure primitives.
- `build123d` (Python on the OpenCascade B-rep kernel) is the best LLM-ergonomic stack for mechanical
  parts and gives **STEP** export — the CAD-grade artifact Adam/mesh-gen lack.
- Every generated part still runs through Phase 0's fit/printability gate before it's "ready" — we are
  not shipping "text → shape"; we're shipping "text → *part that fits and prints*."

## In scope
1. **A sandboxed `code_cad` meshgen provider** — takes agent-authored `build123d` Python, executes it
   in an **isolated subprocess** (hard timeout, no network, temp cwd, resource caps), returns a
   watertight mesh (STL) + STEP + the extracted parameters. Mirrors the `ParametricCadProvider`
   interface so it drops into the existing pipeline.
2. **The execute → render → validate → fix loop** — run code; on a kernel/exec error feed the
   traceback back to the agent to fix (bounded retries); on success run Phase 0
   `fabricate()` / `validate` / `check_fit` and surface the `FabricationReport`.
3. **Parameter extraction (code + JSON params)** — the agent emits code **plus** a JSON parameter
   block (brief §1 — dodges the LLM coordinate-frame failure and powers the editable sliders). Store
   `{code, params}` as the regenerable, editable artifact.
4. **STEP export** alongside STL + the BS-native `.3mf`.
5. **Keep it isolated.** `build123d` is a real dep (OpenCascade) — put it behind an **optional extra**;
   the existing `trimesh` path and the 753-green base suite must pass **without** it (new tests
   skip-if-not-installed).

## Out of scope (later phases)
- Measurement layer / datasheet parts library → Phase 2.
- The schematik-grade SPA + in-product agent UI → Phase 3 (Phase 1's loop is programmatic: CLI/MCP).
- Architecture / `rhino3dm` model-fabrication path → Phase 4.

## The seam (define the contract first, then both code to it)
```python
# Codex owns: src/printpipe/codecad/executor.py  (systems + geometry, security-critical)
@dataclass
class CodeCadResult:
    mesh_path: str | None        # watertight STL
    step_path: str | None        # B-rep STEP
    params: dict                 # extracted parameter block
    stdout: str
    error: str | None            # traceback if execution failed (drives the fix loop)
    watertight: bool

def execute_code_cad(code: str, params: dict, *, timeout_s: float = 20.0) -> CodeCadResult: ...
#   subprocess isolation, no network, temp cwd, resource caps; build123d -> mesh+STEP;
#   validate watertight; never raise on user-code errors -> return them in .error
```
- **Codex owns:** `execute_code_cad` (the sandbox + build123d→mesh/STEP + watertight check) and its
  tests. Treat the sandbox as **untrusted-code execution** — the agent writes the code.
- **Claude owns:** the `code_cad` provider, the execute→render→validate→fix loop, param storage,
  pipeline + MCP wiring, and the agent prompt that authors `build123d`. Codes to `CodeCadResult`;
  does **not** reimplement the sandbox.

## Guardrails
- `build123d` behind an optional extra; base suite green without it.
- Sandbox is security-critical (subprocess, hard timeout, no net, temp cwd, resource caps).
- Preserve Phase 0 (`FabricationReport`) and the **BS-native openable `.3mf`** export (hand-built
  project `.3mf` + headless `--slice` crash this BS build). Local-first, atomic commits, feature branch
  off the just-landed main.

## Acceptance
Given a prompt ("a 40 mm bracket with two M3 holes 25 mm apart"), the agent authors `build123d`
code + params → the sandbox executes it to a watertight mesh + STEP → the loop fixes any execution
error → Phase 0 `fabricate()` validates fit/printability → it exports an openable Bambu `.3mf` — all
programmatically, suite green, `build123d` isolated.

## Kickoffs (fire only after the user OKs this scope)
- **Claude:** "Read `docs/PHASE1_SCOPE.md` (+ your lane in `docs/kickoff_claude.md`). Build the
  `code_cad` provider + execute→render→validate→fix loop + param extraction + pipeline/MCP wiring, to
  Codex's `execute_code_cad` / `CodeCadResult` contract. Branch `claude/phase1-codecad` off main.
  Phase 1 only; stop for my OK before Phase 2."
- **Codex:** "Read `docs/PHASE1_SCOPE.md`. Own `execute_code_cad` (sandboxed `build123d` executor:
  subprocess isolation, timeout, no-net, resource caps) + build123d→mesh/STEP + watertight validation,
  behind the `CodeCadResult` contract, with thorough tests (incl. malicious/looping/over-time code).
  Then review Claude's integration."
