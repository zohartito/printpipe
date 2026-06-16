# PrintPipe — build-agent handoff (START HERE)

> You are an autonomous coding/design agent tasked with building the next version of **PrintPipe**.
> This is the entry point. Read the four docs below in order, then the code, then propose a plan
> before any large rewrite.

## The one-line mission
Make PrintPipe the tool that **designs real, fabricable 3D models that provably FIT and PRINT — by
conversation.** Today it makes hardware enclosures (keep that working); the engine is general; the
moat is the verification/grounding layer no competitor has.

## Read in this order
1. **`docs/PRINTPIPE_AGENT_BRIEF.md`** — what PrintPipe is, the competitive position, the strategy
   (general engine + narrow-deep wedge), and the two fixes. Start here.
2. **`docs/FABRICATION_VERIFICATION_SPEC.md`** — the moat: the fabrication-verification engine
   (consolidate → thicken → validate → printability → orient → pack → export), grounded in real runs.
3. **`docs/research/competitive-research.md`** — the sourced receipts (Adam, Zoo, Schematik, the
   measurement gap, how LLMs make 3D, gen-3D + architecture).
4. **`docs/ARCHITECTURE.md`** + **`docs/APP_ROADMAP.md`** — the current system and existing roadmap
   (align with these; don't contradict them blindly).

Then the code: `src/printpipe/meshgen/enclosure.py`, `parametric_cad.py`, `pipeline/__init__.py`,
`mcp_server.py`, `web/server.py`, and the live worked example
`examples/pi_zero_2w_imx477_camera_case.py` (its `7/7` clash checks are the seed of the verification
engine).

## What to build (phased — propose a plan per phase, keep tests green)

- **Phase 0 — the moat, on the existing engine.** Implement `FabricationReport` + a reusable
  `validate(parts) → valid/total + reasons` (generalize the camera-case clash checks). Add
  **dimension provenance** (`datasheet | measured | scanned | assumed`) and gate "ready to print" on
  no `assumed` fit-critical dims. *This is the highest-value, lowest-risk start.*
- **Phase 1 — general code-gen engine.** Evolve from the fixed `EnclosureSpec` primitives to
  **LLM-authored parametric code** (build123d for parts) run in a sandbox → render → read → fix loop.
  Preserve the BS-native openable `.3mf` export.
- **Phase 2 — measurement layer.** Caliper-first guided capture (one dimension at a time, with a
  diagram) + a **datasheet parts library** (Pi Zero 2W, IMX477, PiSugar, M3/heat-sets, bearings,
  Gridfinity) + reference-scale photo/scan for *layout only* (be honest: not fit).
- **Phase 3 — the real UI.** Replace the inline-HTML `web/server.py` with a clean JSON API + an SPA:
  3-pane studio (chat + param tree / 3D viewport with dimension+clearance overlays / parts + export),
  Schematik-grade instrument aesthetic (see brief §5 for tokens), Zookeeper-grade agent behavior.
- **Phase 4 — architecture model fabrication (near-term, same engine).** rhino3dm/Grasshopper:
  unroll → thicken → validate → plate/sheet-pack → export print + laser DXF (CUT/ETCH/FOLD). The
  user's ARCH 202B pipeline (brief §4.5) is the reference. **Architecture design/BIM is NOT in scope.**

## Guardrails
- Keep the existing pipeline + tests green. Preserve the **BS-native openable `.3mf`** path — the
  hand-built project `.3mf` and headless `--slice` both crash this Bambu Studio build; the working
  path is STL + inheriting presets → let Bambu Studio export its own `.3mf` (+ `--arrange`).
- Local-first, dependency-sane. Don't add heavyweight infra the user didn't ask for.
- Don't compete on "text → shape" (Adam/Zoo own it). Every phase should deepen **fit + fabrication**.
- Propose a plan before large rewrites.

## Acceptance (what "done" looks like)
In the browser, a user describes a part, is asked only for the few real measurements it needs, refines
it conversationally ("flip the ports", "lens inside", "raise it so the ribbon folds"), watches the
clearance/printability status go green, and exports an **openable Bambu `.3mf`** — without touching
Python, in a UI that reads like a precision instrument.
