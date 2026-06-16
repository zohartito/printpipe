# PrintPipe — product & strategy brief (v3, research-grounded)

> Hand this whole file to a capable coding/design agent in the `printpipe` repo. It defines what
> PrintPipe is, how AI actually makes 3D (the engine to build), where the defensible moat is, the
> narrow-deep-on-a-general-core strategy, and the two things to fix first (real-dimension grounding +
> a real UI; design north star https://www.schematik.io). Read the codebase and re-skim the
> competitors before large changes.

---

## 0. Mission

PrintPipe = AI that designs **real, fabricable 3D models that provably FIT and PRINT** — by
conversation. Today it makes hardware enclosures (keep that working). The **engine is general** — it
generates editable parametric geometry *code*, the same mechanism that already makes great models in
Codex/Opus — so it can grow to brackets, fixtures, and eventually architecture. But the **moat and
go-to-market are narrow-deep**: own the one thing no competitor holds — *geometry guaranteed to fit
real hardware and print correctly.*

---

## 1. How AI actually makes 3D — this IS the engine to build

Frontier LLMs (GPT-5.x/Codex, Claude/Opus) **do not emit meshes** — they **write procedural geometry
code** that a kernel executes. That is exactly why architecture models made by prompting Opus/Codex
look great: the model wrote Python / Grasshopper / Blender that built exact geometry. Build PrintPipe
on this, not on mesh generation.

- **Stacks the LLM should emit** (by domain):
  - **Hardware / mechanical parts → build123d** (Python on the OpenCascade **B-rep** kernel: NURBS,
    fillets, **STEP** export). Best LLM ergonomics + true CAD. Keep **OpenSCAD-WASM** as a light
    in-browser preview/fallback (the Adam/CADAM pattern). `trimesh` (today's PrintPipe) stays for CSG.
  - **Architecture / massing → Blender `bpy`** (visual) and **Rhino + Grasshopper Python** (NURBS,
    your studio workflow). `Three.js` for the web viewport.
- **The proven product loop:** model emits **code + a JSON parameter block** → **execute in a
  sandbox/WASM** → **render** → **read the render + kernel errors** → **auto-fix** → params become
  live sliders. (Real examples: Adam/CADAM OpenSCAD-WASM + Three.js; Zoo KCL; build123d-mcp /
  cad-khana; Blender-MCP; RhinoMCP `execute_code` + `capture_viewport`.)
- **Known failure + the fix:** LLMs are weak at raw 3D coordinate frames (Z-up vs Y-up training
  conflict). Don't make the model reason in 3D — have it emit **parameters/JSON + a deterministic
  assembly step**, and validate by reading the render.
- **Implication for PrintPipe:** evolve from today's fixed `EnclosureSpec` dataclass primitives →
  **general LLM-authored parametric code** (build123d for parts; bpy/Grasshopper for architecture) in
  that execute-render-validate-fix loop. **Geometry generation is commoditizing** (Adam, Zoo, every
  code-gen repo do it) — don't over-invest there. Invest in the layer *below* it (§3).

---

## 2. The landscape & the empty intersection (researched 2026)

- **Native generative-3D** (Meshy, Tripo, Microsoft TRELLIS, Tencent Hunyuan3D, Rodin/Hyper3D):
  gorgeous textured **meshes, but dimensionless** — "print-ready" means *sliceable*, not *fits the
  real part*. Useless for parts/architecture precision. (Reserve only for decorative organic assets.)
- **Text-to-CAD** (Adam/AdamCAD — OpenSCAD code + sliders, $4.1M; Zoo/KCL — B-rep + Zookeeper agent):
  real parametric solids + STEP, **but no fit/fabrication loop** — they don't ingest a real reference
  part, enforce clearances, or close the print-tolerance loop.
- **AI-for-architecture** (TestFit, Autodesk Forma, Architechtures, Finch 3D, Hypar, Veras, plus
  LLM-in-Grasshopper like "Ant"): BIM / feasibility / massing — a **different representation (BIM)**
  and **different constraint universe (zoning/IBC)**, defended by entrenched incumbents.
- **Schematik** (north star, not a competitor): "Cursor for Hardware" (firmware + wiring), no CAD.

**The intersection nobody owns:** *AI geometry guaranteed to fit a real physical object and print
correctly* — real dimensions + fit/clearance to existing hardware + print-tolerance compliance.
Gen-3D has no dimensions; text-to-CAD has no fit loop; architecture is a separate universe. **That
empty intersection is PrintPipe's product.**

---

## 3. The moat = grounding + verification (Fix #1 — the headline feature)

Geometry generation is a commodity; **the defensible layer is the one wrapped around it.** Principle:
**the agent never silently guesses a fit-critical dimension, and the UI always shows measured vs
guessed.**

1. **Provenance on every dimension** — `datasheet | measured | scanned | assumed` + confidence.
   Assumed/scanned fit-critical dims are flagged and **block "ready to print"** until confirmed.
   *No competitor does this; it fixes the documented "looks right, fails dimensional check" failure.*
2. **Caliper-first capture** — the agent asks for one specific measurement at a time with a diagram
   ("lens length: board face → front tip"); optional Bluetooth-caliper bridge. This — not scanning —
   is how fit is guaranteed.
3. **Datasheet-backed parts library as a fit constraint** — seed real components (Pi Zero 2 W, IMX477,
   PiSugar, M3 screws, heat-set inserts, bearings, Gridfinity) from official drawings; "design a mount
   for an M3 cap screw / this Pi" pulls exact dims and designs *around* them with **named clearance
   presets** (FDM 0.2 mm fit). McMaster-class data exists but no chat-CAD tool wires it in.
4. **Reference scanning — for layout, not fit (be honest):** photo-with-scale or phone scan captures
   the **envelope / where things are** (~cm accuracy); **fit-critical dims still come from
   calipers/datasheets.** Degrade gracefully on sparse scans (the "15 points not 30" case) and say
   what to re-measure.
5. **In-loop fit/clearance/printability checker** (productize what cad-khana/CADSmith prove):
   interference + clearance + wall-thickness + overhang + **print tolerance / material shrinkage**
   against *the user's* Bambu nozzle/material, before export. Live green/amber/red, with which
   clearances depend on an `assumed` number. (We already do ad-hoc clash checks in the camera-case
   script — generalize them into the engine.)

**Acceptance:** a user designs a correct-fit part for hardware they physically have; every load-
bearing dim is datasheet/measured (or flagged assumed); clearance check is green; the `.3mf` opens
and prints.

---

## 4. Strategy: narrow-deep wedge on a general engine

Both research streams converge here.

- **Win narrow-deep first:** own **fit-to-real-hardware enclosures + Bambu print.** The moat is the
  constraint data + verification loop — exactly where gen-3D (no dims) and text-to-CAD (no fit) are
  weak. High-pain, willing-to-pay niche (hardware startups, makers, IoT). This is what keeps users
  from "just going to a competitor" — the competitors can't make it *fit*.
- **Generalize along the manufacturing axis** where the same fit/tolerance moat compounds: enclosures
  → brackets → mounts → fixtures → mechanical parts.
- **Split "architecture" in two** (the user's real ARCH 202B corpus proves the line — see §4.5):
  - **Architecture MODEL FABRICATION** — Rhino model → thicken to printable walls / unroll to laser
    panels → validate → pack onto plates/sheets → orient → export STL/DXF. **This IS PrintPipe's core**
    (same parametric-code → validate → pack → fabricate pipeline as enclosures; same fit/printability
    moat). A *near-term* extension along the manufacturing axis, not a separate bet.
  - **Architecture DESIGN / BIM** (floor plans, massing, zoning, feasibility) — different
    representation (BIM), different constraints (code/zoning), entrenched incumbents (Forma/Autodesk,
    TestFit). **Defer this** — going broad early commoditizes you into the mesh-gen price race.

One line: **don't compete on "type text → get a shape" (Adam/Zoo own that). Win on "designs parts
that fit the hardware in your hand, and print."**

---

## 4.5 Ground truth: the ARCH 202B fabrication pipeline (real evidence the strategy is right)

The user's own architecture studio project (Villach Sports Hall, ~237 GB on an external drive) is
PrintPipe's exact pipeline — done by hand. It validates every claim above:

- **Parametric Rhino model** — facade banded "returns", roof as
  `roof_z(y) = 55.71 + (34.88 - y) * 0.1224` (a ~7° parametric slope hard-coded into the scripts).
- **~95 versioned, LLM-written `rhino3dm` Python scripts** (`punch_south_returns_v39`,
  `fix_flat_returns_v42`, `split_south_return_band_v46`, `west_punched_vholes_flat_returns_v51`,
  `thick_clt_panels_roof_shs_v66`, `fix_east_subframe`, …). Each is a **prompt → code → run → fix**
  iteration. *This is PrintPipe's conversational model-iteration loop, performed manually with
  Codex/Opus, one throwaway script at a time.*
- **Two fabrication targets from one model:**
  (a) **3D print** — offset surfaces to **0.66 mm walls → validate closed solids → pack onto 250×250
  plates → export STL** (a real run logged "Valid closed solids: **16 / 19**" — three returns failed
  the offset; **that validity failure is exactly what PrintPipe must catch and explain**).
  (b) **Laser-cut CLT** — `unroll_subdivision.py` unrolls to flat panels with layered
  **CUT / ETCH / FOLD / score** semantics, packed onto **12×12 sheets**, scaled to 1:24.
- **The pain PrintPipe removes:** the failed offsets (16/19), the proliferation of
  `DO_NOT_USE … orientation …` vs `REAL … CORRECT UPRIGHT … EDGE ON BED` folders (manual orientation
  trial-and-error), plate/sheet packing, and the 95-version script sprawl.

**Implication:** PrintPipe = collapse that (95 scripts + DO_NOT_USE folders) into **one conversational,
verified loop** — thicken / validate / pack / orient, with the failures caught and explained, exporting
to **both 3D print and laser**. The verification moat (solid validity, wall thickness, packing,
orientation, fit) is **identical** across hardware enclosures and architecture model fabrication —
which is why model fabrication is the natural near-term extension, and BIM is not.

---

## 5. Fix #2 — a real UI (north star: schematik.io)

**Study https://www.schematik.io first.** Adopt Adam/Zoo's standard layout + Schematik's instrument
aesthetic + Zoo Zookeeper's agent behavior.

- **Layout (3-pane):** left = conversation + live editable **parameter tree** (each dimension shows
  its provenance tag); center = **3D viewport** with section views, dimension lines, and
  clearance/clash badges (a live inspectable surface, not a passive render); right = **parts +
  measurements** ("needs measurement" queue) + **export/slice**.
- **Design language:** dark "instrument" canvas (`#141414`/`#161616`) + warm paper (`#f0ece3`) + one
  or two electric accents (periwinkle `#7d80ff`, lime `#c8e86a`) + a **dedicated red/amber ramp for
  tolerance/clearance violations**. **Monospace is load-bearing** (Space Grotesk) for every number.
  Prompt-first entry, tabbed panels, strong grid, real units everywhere. No gradient blobs,
  glassmorphism, emoji, or pastel chat bubbles. Carry the technical voice everywhere.
- **Agent behavior (Zookeeper-grade):** conversational like a teammate, **asks clarifying questions**
  (especially "what's the real dimension?"), selection/project-aware, **inspects + validates geometry
  mid-loop** (CADSmith-style fix-errors-inner / validate-against-measurements-outer), shows a compact
  **diff of changed parameters** each edit.

---

## 6. What's already built (keep) and what to evolve

- **Keep:** the pipeline; the slicer **settings API** (`resolve_slice_settings`, `process_overrides`)
  + **MCP server** (`mcp_server.py`); the hard-won **BS-native openable `.3mf`** export (STL +
  inheriting presets → Bambu Studio exports its own `.3mf`; hand-built project `.3mf` and headless
  `--slice` crash this BS build — don't regress).
- **Evolve:** today's fixed parametric primitives in `meshgen/enclosure.py` + `parametric_cad.py` →
  **general LLM-authored parametric code** (build123d for parts; bpy/Grasshopper for architecture) in
  the sandboxed execute-render-validate loop of §1. Generalize the camera-case clash checks into a
  reusable verification engine (§3.5).
- **Replace:** the inline-HTML `http.server` (`web/server.py`) → a clean JSON API + a real frontend
  SPA with a WebGL viewport (Three.js / react-three-fiber).

---

## 7. Deliverables & guardrails

- A general parametric **code-gen engine** with the execute-render-validate-fix loop (parts first;
  architecture-capable).
- The **grounding/verification moat**: provenance + gating, caliper-first capture, datasheet parts
  library, reference-scale photo/scan for layout, in-loop clearance/print-tolerance checker.
- The schematik-grade **3-pane UI** + Zookeeper-grade in-product agent wired to the engine's
  geometry/measurement/settings/export APIs.
- Clean backend API; existing pipeline + tests stay green; preserve the BS-native `.3mf` export; keep
  local-first and dependency-sane. **Architecture is roadmap, not v1.**

**Start by reading:** `meshgen/enclosure.py`, `parametric_cad.py`, `pipeline/__init__.py`,
`mcp_server.py`, `web/server.py`, `examples/pi_zero_2w_imx477_camera_case.py` (live worked example +
clash checks). Propose a plan before any large rewrite.
