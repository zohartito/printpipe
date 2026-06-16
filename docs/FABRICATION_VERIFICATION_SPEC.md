# PrintPipe — Fabrication-Verification engine spec

> The shared layer that turns *any* parametric model (hardware enclosure **or** architecture study
> model) into **validated, fabricable output** — and catches what won't fabricate, with a reason.
> This is PrintPipe's moat (per `PRINTPIPE_AGENT_BRIEF.md` §3–4.5): geometry generation is a
> commodity; **the verification + grounding layer is the product.**
>
> Grounded in two real, working sources in this account:
> - **Hardware path** — PrintPipe's existing engine (`meshgen/enclosure.py` clash checks; the
>   BS-native openable `.3mf` export; watertight validation).
> - **Architecture path** — the user's ARCH 202B "Villach Sports Hall" pipeline (a print run logged
>   `Valid closed solids: 16/19`; `unroll_subdivision.py` unrolls to layered laser panels). The exact
>   parameters below are taken from those runs.

---

## 0. The one idea

A model becomes *fabricable* only after it passes a fixed sequence of checks. PrintPipe runs that
sequence on every generated/edited model, **reports valid-vs-failed with reasons**, and the in-product
agent can converse about the flags ("3 of 19 returns won't thicken at 0.66 mm — their surfaces
self-intersect; raise wall thickness or split them"). Same sequence for enclosures and for
architecture model fabrication; only the defaults differ.

---

## 1. Pipeline stages (each emits a structured, provenance-tagged report)

**Input:** a parametric model — either watertight meshes (today's `trimesh`/STL engine) or open
surfaces / breps (the architecture case; `rhino3dm` / build123d).

1. **Consolidate / join.** Join loose surfaces into shells over a **tolerance sweep**, pick the
   variant with the fewest-but-valid shells.
   - *202B evidence:* `Join tol 0.01 → 15 shells`, `Join tol 0.05 → 19 shells`; it chose 0.05.
   - *Mesh case:* weld/merge vertices, split into connected components, label parts.
   - Report: shells found per tolerance, chosen tolerance, per-shell face/edge counts.

2. **Thicken (offset-to-solid).** Give open surfaces a wall thickness `t`; offset each shell to a
   closed solid. **Primary failure mode to catch:** when a surface normal flips or self-intersects,
   the offset returns **0 parts**. Try `+t`, then `-t`; if both fail, flag the part as
   **un-thickenable** with the reason.
   - *202B evidence:* `Return N offset used distance: 0.66` (success) vs `offset used distance:
     -0.66 → offset parts: 0` for returns 6, 14, 16 (failed). `t = 0.66 mm`.
   - Report: per part — direction used, parts produced, output face/edge counts, solid? valid?

3. **Validate (the headline check).** Per part: **closed · manifold · solid · valid**. Aggregate to
   `valid / total` and, for each failure, the *why* + a suggested fix.
   - *202B evidence:* `Valid closed solids: 16 / 19`.
   - *Hardware evidence:* PrintPipe already does watertight + the camera-case 7/7 clash checks —
     fold those in here.

4. **Wall-thickness & printability.** Every wall `≥ min printable` (FDM nozzle/material) and
   `≥ laser kerf`; flag overhangs/bridges/unsupported spans, thin features, trapped volumes.
   Reference the **dimension provenance** (brief §3): a wall whose thickness depends on an `assumed`
   dimension is flagged amber.

5. **Orient.** Generate candidate orientations and **score** them; recommend one, let the
   agent/user override.
   - *202B evidence:* the manual orientation graveyard — `DO_NOT_USE … west returns upright
     orientation …` vs `REAL … CORRECT UPRIGHT SUBFRAME EDGE ON BED` vs `… FLAT OUTER FACE`. Automate
     this choice: score by support volume, bed-contact stability, and surface quality on show faces.

6. **Pack / nest.** Bin-pack the valid parts onto **fabrication units**, centered, spilling to more
   units as needed.
   - *Print:* plate **fit box 250 × 250 mm**; multiple plates (202B run: Plate 1 = 12 parts, Plate 2
     = 4; each `centered`). Report plate count, contents, packing efficiency, what didn't fit.
   - *Laser:* sheets **12 × 12 in** with margins/kerf.

7. **Export.**
   - *Print:* STL per plate **+ the BS-native openable `.3mf`** (existing path: STL + inheriting
     presets → Bambu Studio exports its own `.3mf`; never the crashing hand-built project `.3mf`).
   - *Laser:* DXF/SVG with **layered semantics from `unroll_subdivision.py`** — `CUT` (cut-through),
     `ETCH_OPAQUE / ETCH_TRANS / ETCH_SCREEN / ETCH_MAJOR` (treatment bands), `FOLD` (score lines),
     `FLOOR_REF`, `LABELS`, `ROOF_CUT / ROOF_ETCH` — plus a scale factor (202B: output in feet,
     ×0.5 → 1:24).

---

## 2. Output contract (what every run returns)

```
FabricationReport
  units, tolerance, wall_thickness, target            # print | laser
  parts: [ { id, source_faces, thicken_dir, solid, valid, failure_reason? } ]
  valid_solids: "16 / 19"                              # headline
  printability: [ { check, status: pass|flag, detail, depends_on_assumed_dim? } ]
  orientation: { recommended, candidates:[{name, support_vol, stability, score}] }
  packing: { unit: "250x250 plate" | "12x12 sheet", units_used, layout, efficiency, unplaced[] }
  exports: { stl[], openable_3mf?, dxf_layers? , scale }
  agent_summary: "plain-English explanation of every flag"   # for the chat panel
```

Every flag carries a *reason* and (where possible) a *fix the agent can offer* — so the conversation
is "here's what won't fabricate and how to fix it," not a silent failure.

---

## 3. What PrintPipe already has vs. what to build

| Stage | Exists today | To build |
|---|---|---|
| Consolidate/join | mesh merge_vertices | surface/brep join + tolerance sweep |
| Thicken (offset-to-solid) | — | offset ±t, both-direction retry, un-thickenable flag |
| Validate | watertight check; camera-case clash checks (7/7) | generalize into a reusable `validate(parts)` returning `valid/total` + reasons |
| Wall-thickness/printability | clearance/clash in the recipe | min-wall / overhang / kerf checks vs the user's nozzle+material |
| Orient | manual (in the recipe) | candidate generation + scoring |
| Pack/nest | single part on bed | bin-pack to 250×250 plates / 12×12 sheets, multi-unit |
| Export | BS-native `.3mf`; ASCII STL | per-plate STL/`.3mf`; laser DXF with CUT/ETCH/FOLD layers |

Engine direction (brief §1): the agent emits **parametric code** (build123d for parts, rhino3dm /
Grasshopper for architecture), and this verification layer runs on the result — replacing the user's
manual "~95 versioned scripts + DO_NOT_USE orientation folders" with one conversational, verified loop.

---

## 4. Seed defaults (from the real runs)

- **Wall thickness:** 0.66 mm (model-scale architecture, 202B); 1.2–2.4 mm (FDM hardware walls).
- **Join tolerance sweep:** 0.01 / 0.05 mm → pick fewest-valid shells.
- **Plate fit box:** 250 × 250 mm (print). **Laser sheet:** 12 × 12 in.
- **Model units:** mm, tol 0.01. **Laser export:** feet, scale ×0.5 → 1:24 (configurable per model).
- **Orientation candidates:** flat-outer-face, upright-edge-on-bed (extend per part class).

## 5. Acceptance

Given a messy parametric model (open surfaces or mesh), the engine returns: valid solids + flagged
failures **with reasons** (the `16/19` case), an orientation recommendation, a plate/sheet packing,
and exported print + laser files — and the agent can explain every flag in chat and offer the fix.

---

## 6. The interface contract (BOTH agents start here)

This is the seam between the two agents. **Codex** implements the geometry functions; **Claude** builds
the pipeline/UI/agent that calls them. Both import these dataclasses — **do not invent a parallel data
model.** Suggested home: `src/printpipe/fabrication/report.py`.

```python
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum

class Provenance(str, Enum):
    DATASHEET = "datasheet"; MEASURED = "measured"; SCANNED = "scanned"; ASSUMED = "assumed"

class Status(str, Enum):
    PASS = "pass"; FLAG = "flag"; FAIL = "fail"     # FLAG = printable but notable; FAIL = blocks

class Target(str, Enum):
    PRINT = "print"; LASER = "laser"

@dataclass(frozen=True)
class Dimension:
    name: str
    value_mm: float
    provenance: Provenance
    fit_critical: bool = False        # ASSUMED + fit_critical  ->  blocks ready_to_print
    confidence: float = 1.0           # 0..1
    source: str = ""                  # datasheet ref / "caliper 2026-06-15" / scan id

@dataclass
class PartResult:
    id: str
    source_faces: int
    thicken_dir_mm: float | None      # +t, -t, or None if not thickened
    solid: bool
    valid: bool
    failure_reason: str | None = None # why thicken/validate failed (the 3 of 19)

@dataclass
class Check:
    name: str                         # "min_wall" | "overhang" | "kerf" | "interference" | "clearance"
    status: Status
    detail: str
    depends_on_assumed_dim: str | None = None   # name of an ASSUMED Dimension, if any

@dataclass
class OrientationCandidate:
    name: str                         # "flat_outer_face" | "upright_edge_on_bed" | ...
    support_volume_mm3: float
    stability: float                  # footprint / CoM heuristic, 0..1
    score: float

@dataclass
class PackingResult:
    unit: str                         # "250x250 plate" | "12x12 sheet"
    units_used: int
    layout: list[dict]                # per-unit part placements
    efficiency: float                 # 0..1
    unplaced: list[str] = field(default_factory=list)

@dataclass
class ExportResult:
    stl_paths: list[str] = field(default_factory=list)
    openable_3mf: str | None = None   # the BS-native openable export
    dxf_layers: list[str] = field(default_factory=list)   # CUT / ETCH_* / FOLD / LABELS / ...
    scale: float = 1.0

@dataclass
class FabricationReport:
    units: str
    tolerance_mm: float
    wall_thickness_mm: float
    target: Target
    dimensions: list[Dimension]
    parts: list[PartResult]
    valid_solids: str                 # "16 / 19"
    printability: list[Check]
    orientation: OrientationCandidate | None
    packing: PackingResult | None
    exports: ExportResult
    agent_summary: str                # plain-English explanation for the chat panel

    @property
    def ready_to_print(self) -> bool:
        if any(c.status is Status.FAIL for c in self.printability):
            return False
        if any(not p.valid for p in self.parts):
            return False
        if any(d.provenance is Provenance.ASSUMED and d.fit_critical for d in self.dimensions):
            return False                 # a fit-critical guessed dimension blocks readiness
        return True
```

**Function seam (who owns what):**

```python
# ---- Codex owns: pure geometry math, behind this contract, with tests ----
def thicken_to_solids(shells, wall_mm: float) -> list[PartResult]: ...   # offset ±t, retry on fail
def validate(parts) -> list[PartResult]: ...                            # closed/manifold/solid/valid
def score_orientations(part) -> list[OrientationCandidate]: ...
def pack(parts, unit: str) -> PackingResult: ...                        # bin-pack to plate/sheet

# ---- Claude owns: the pipeline that assembles the report + the UI/agent ----
def fabricate(model, target: Target, settings) -> FabricationReport: ...
```

Phase 0 = ship `FabricationReport` + `validate(...)` (generalized from the camera-case clash checks) +
`Dimension` provenance and `ready_to_print`. Everything else hangs off this contract.
