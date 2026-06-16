# PrintPipe — competitive & technical research (receipts)

> Compiled from five deep-dive research agents (2026). Every claim is sourced inline. This is the
> evidence base for `docs/PRINTPIPE_AGENT_BRIEF.md` and `docs/FABRICATION_VERIFICATION_SPEC.md`.

---

## 1. Adam / "AdamCAD" — the direct text-to-CAD competitor

- **adam.new** (alias adamcad.com). YC **W25**, SF, founded 2025, $4.1M seed (Oct 2025, TQ Ventures;
  angels incl. Tim Glaser/PostHog, Theo Browne) — ~$6M total. Founders Aaron Li (industrial design)
  + Zach Dive (ex-Adept). ([TechCrunch](https://techcrunch.com/2025/10/31/yc-alum-adam-raises-4-1m-to-turn-viral-text-to-3d-tool-into-ai-copilot/), [YC](https://www.ycombinator.com/companies/adam))
- **Approach:** text → **OpenSCAD code → OpenSCAD-WASM (in-browser) → Three.js**, auto-extracted
  **parameter sliders**; conversational (part-select + prompt, "inpainting style"), feature tree.
  Confirmed by their open-source **`Adam-CAD/CADAM`** repo (GPL-3.0; React 19/TanStack, R3F, Supabase,
  **Claude API**). ([CADAM repo](https://github.com/Adam-CAD/CADAM), [review](https://pasqualepillitteri.it/en/news/3372/adamcad-text-to-cad-ai-review-2026))
- **Export:** STL/OBJ/SCAD (DXF in CADAM); **STEP on roadmap, not shipped**; no slicer integration.
- **Accuracy gap (the opening):** "very accurate on explicit dims, less accurate on implicit ones";
  **no measurement input, no reference-part library beyond generic OpenSCAD libs (BOSL/MCAD), no
  tolerance/fit engine.** ([review](https://pasqualepillitteri.it/en/news/3372/adamcad-text-to-cad-ai-review-2026), [aiagents.saastrac.com](https://aiagents.saastrac.com/ai-agent/adamcad/))
- **Pricing:** Free / $5.99 / $17.99. **Traction:** >1M models, tens of thousands of users.
- **Direction:** pivoting to a CAD-plugin agent (Onshape/Fusion). Named competitors: Zoo/KittyCAD,
  MecAgent, CADGPT.
- **Takeaway:** match their chat-left/3D-right + auto-sliders layout; **do not** fight them on
  "text→shape." Win on fit + fabrication, which they lack.

## 2. Schematik — design north star, NOT a CAD competitor

- **schematik.io**, "**Cursor for Hardware**" — plain English → **firmware + wiring diagram + BOM +
  assembly** for Arduino/ESP32/Pico. **Not CAD, no 3D print.** $4.6M pre-seed (Lightspeed, Apr 2026);
  founder Samuel Beek (ex-VEED). 100k+ users. ([funding](https://www.schematik.io/blog/schematik-raises-4-6m-pre-seed), [schematik.io](https://www.schematik.io))
- **Why it matters = UX/design language to emulate** (from its CSS tokens):
  - Dark "instrument" canvas `#141414`/`#161616`; warm paper `#f0ece3`; accents **periwinkle `#7d80ff`
    + lime `#c8e86a`**; red/amber OKLCH ramps for status/warnings. ([CSS](https://www.schematik.io/_next/static/css/27a796b2e06605c5.css))
  - Fonts: display **"Vanity"**, body **"Universal Sans"**, **"Space Grotesk" mono (load-bearing)**.
  - **React Flow** node-graph wiring canvas (live, inspectable, not a static image).
  - Prompt-first hero ("what are we making today?"), tri-tab **Code | Wiring | Assembly**, voice
    everywhere (the 404 is a serial monitor).
- **Trust model:** grounded in a real **5,941-part catalogue**; founder's line — "electronics is pure
  physics, so you can actually check." **No dimensions/tolerances/simulation.** ([parts](https://www.schematik.io/parts), [WIRED via Promptrofy](https://promptrofy.com/2026/04/19/schematik-is-cursor-for-hardware-anthropic-wants-in/))

## 3. AI / text-to-CAD landscape + the measurement gap

- **Zoo.dev / KittyCAD** — **KCL parametric code → real B-rep**; **Zookeeper** agent (Jan 2026) is the
  best agentic CAD UX: asks clarifying Qs, inspects/snapshots/debugs geometry, project-aware. STEP/STL.
  ([zookeeper](https://zoo.dev/research/zookeeper), [KCL](https://zoo.dev/research/introducing-kcl))
- **build123d / CadQuery + LLM** (research: **cad-khana**, **CADSmith**) — closest to fit-aware:
  cad-khana emits **`diagnostics.json`** (interference, clearance, wall thickness, overhang) as **build
  failures**; CADSmith iterates against exact OpenCascade measurements + a VLM judge "until
  dimensionally correct." ([cad-khana](https://github.com/cyberchitta/cad-khana), [CADSmith](https://www.alphaxiv.org/overview/2603.26512v1))
- **Mesh-gen** (Meshy/Tripo/etc.) — **dimensionally blind**; "print-ready" = sliceable, not fits.
- **The cross-cutting GAP (PrintPipe's wedge):** no mainstream tool does **measured-vs-guessed
  provenance**, **datasheet-backed parts as a fit constraint**, or an **in-loop clearance/print-
  tolerance check**. Documented failure mode: AI parts "look roughly correct but fail basic
  dimensional checks," and tools "don't know your printer." Phone/LiDAR scanning is **below
  engineering tolerance (~cm error)** — calipers/datasheets are the credible accuracy path. ([colabsoftware](https://www.colabsoftware.com/guides/ai-tools-for-cad-standards-enforcement-your-complete-guide-to-automated-compliance-2026), [getleo](https://www.getleo.ai/blog/best-text-to-cad-tools-3d-printing), [3dmag LiDAR](https://www.3dmag.com/3d-wikipedia/phone-3d-scanning-lidar-iphone-3d-apps-guide/))

## 4. How frontier LLMs actually make 3D (the engine to build)

- LLMs (Codex/GPT-5.x, Opus) **do not emit meshes — they write procedural geometry CODE** a kernel
  executes. Best stacks: **build123d/CadQuery** (Python B-rep, STEP) for parts; **Blender `bpy`** +
  **Rhino/Grasshopper Python** for architecture; OpenSCAD (simple), Three.js (web). ([LLM-for-CAD survey](https://arxiv.org/pdf/2505.08137))
- **Proven loop:** emit **code + JSON params → execute in sandbox/WASM → render → read render +
  kernel errors → auto-fix →** params become sliders. (Adam/CADAM OpenSCAD-WASM; Zoo KCL;
  **build123d-mcp**, **cad-khana**; **Blender-MCP**; **RhinoMCP** `execute_code`+`capture_viewport`.)
  ([CADAM](https://github.com/Adam-CAD/CADAM), [blender-mcp](https://github.com/ahujasid/blender-mcp), [rhinomcp](https://github.com/jingcheng-chen/rhinomcp))
- **Known failure + fix:** LLMs are weak at raw 3D coordinate frames (Z-up vs Y-up training conflict)
  → emit parameters/JSON + a deterministic assembly step; validate by reading the render. ([why LLMs fail at OpenSCAD](https://dev.to/alanwest/why-llms-fail-at-openscad-code-generation-and-how-to-fix-it-2bel))

## 5. Generative-3D & AI-architecture landscape

- **Native gen-3D** (Meshy, Tripo, Microsoft **TRELLIS**, Tencent **Hunyuan3D 2.x**, **Rodin/Hyper3D**;
  Luma Genie **sunset Jan 2026**): mesh/PBR, **dimensionless**. Rodin best topology; Meshy most
  balanced product (1-click Bambu/3MF, still un-dimensioned); Hunyuan3D = open-source SOTA. ([Meshy](https://www.meshy.ai/blog/best-ai-tools-for-3d-printing), [Hunyuan3D](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1), [Rodin Gen-2](https://hyper3d.ai/blog/rodin-gen-2))
- **AI-architecture:** **TestFit** (developer feasibility — where the money is), **Autodesk Forma**
  (massing+analysis, distribution), **Architechtures**/**Finch 3D** (plan→BIM), **Hypar**
  (function-based), **Veras** (AI render of BIM), LLM-in-Grasshopper (**Ant**). Representation = **BIM**,
  constraints = **zoning/code** — a different universe, entrenched incumbents. ([TestFit](https://www.testfit.io/), [Forma](https://www.autodesk.com/products/forma), [Hypar](https://aecmag.com/ai/hypar-text-to-bim-and-beyond/), [Ant for GH](https://blog.rhino3d.com/2026/02/ant-your-ai-copilot-for-grasshopper-new.html))
- **The empty intersection nobody owns:** *AI geometry guaranteed to fit a real physical object and
  print/fabricate correctly* — real dims + fit/clearance to existing hardware + fabrication tolerance.
  Gen-3D has no dims; text-to-CAD has no fit loop; architecture is a separate universe.

---

## Strategic synthesis (the one page)

- **Engine = general LLM code-gen** (build123d for parts; bpy/Grasshopper for architecture) in an
  execute-render-validate-fix loop. Geometry generation is **commoditizing** — don't over-invest there.
- **Moat = the verification/grounding layer** (measured-vs-guessed provenance + datasheet parts +
  in-loop fit/clearance/print-tolerance). This is the empty intersection.
- **Go-to-market = narrow-deep:** own **fits-real-hardware + prints**. Generalize along the
  *manufacturing* axis (enclosures → brackets → fixtures → **architecture model fabrication**, which is
  the same pipeline). **Defer architecture design/BIM** (different rep, codes, incumbents).
- **One line:** don't compete on "type text → get a shape" (Adam/Zoo own it). Win on **"designs parts
  that fit the hardware in your hand, and fabricate."**
