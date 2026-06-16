# Kickoff — Claude Code (primary builder)

> Paste this into a fresh Claude Code session opened in the `printpipe` repo. (Or just say:
> "read `docs/kickoff_claude.md` and do it.")

---

You are the **primary builder** for PrintPipe. Read `docs/AGENT_HANDOFF.md` and everything it links
(`docs/PRINTPIPE_AGENT_BRIEF.md`, `docs/FABRICATION_VERIFICATION_SPEC.md`,
`docs/research/competitive-research.md`), plus the code it points to
(`src/printpipe/meshgen/enclosure.py`, `parametric_cad.py`, `pipeline/__init__.py`, `mcp_server.py`,
`web/server.py`, `examples/pi_zero_2w_imx477_camera_case.py`).

**Your lane:** the pipeline, the engine integration, the in-product agent, and the UI. **Not** the
geometry verification math — Codex owns that (offset-to-solid, validity, nesting, orientation scoring)
behind the `FabricationReport` contract in the spec (§6). Code *to* that contract; don't reimplement it.

**Do Phase 0 only, then stop for my OK:**
1. Propose the plan **and** finalize the `FabricationReport` interface (start from spec §6) — wait for
   my confirmation before writing implementation.
2. Implement `validate(parts) → valid/total + reasons` by **generalizing the camera-case clash checks**
   in `enclosure.py`/the recipe into a reusable function returning `PartResult`s.
3. Add **dimension provenance** (`datasheet | measured | scanned | assumed`) and the `ready_to_print`
   gate (a fit-critical `assumed` dim blocks readiness).
4. Tests for all of it. Keep the existing suite green.

**Guardrails:** work on a feature branch; commit atomically; preserve the **BS-native openable `.3mf`**
export (the hand-built project `.3mf` and headless `--slice` both crash this Bambu Studio build — the
working path is STL + inheriting presets → Bambu Studio exports its own `.3mf` + `--arrange`); keep it
local-first and dependency-sane; **do not start Phase 1+ until I confirm.**

After Phase 0, the roadmap (handoff) is: Phase 1 general code-gen engine (build123d) → Phase 2
measurement layer → Phase 3 the schematik-grade UI + agent → Phase 4 architecture model-fabrication.
Don't compete on "text → shape"; every phase deepens **fit + fabrication**.
