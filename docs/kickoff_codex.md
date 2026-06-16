# Kickoff — Codex (plan reviewer + verification-math module)

> Paste this into a fresh Codex session opened in the `printpipe` repo. (Or: "read
> `docs/kickoff_codex.md` and do it.")

---

You are the **reviewer + geometry-verification specialist** for PrintPipe. Read
`docs/AGENT_HANDOFF.md`, `docs/FABRICATION_VERIFICATION_SPEC.md`, and `docs/PRINTPIPE_AGENT_BRIEF.md`,
plus `src/printpipe/meshgen/enclosure.py` and `examples/pi_zero_2w_imx477_camera_case.py` (its `7/7`
clash checks are the seed of the verification engine).

**Two jobs:**

1. **Review (do this first).** Critique the plan in `docs/AGENT_HANDOFF.md` and the `FabricationReport`
   interface (spec §6) that Claude proposes. Flag architecture, correctness, and edge-case risks
   (degenerate geometry, non-manifold input, offsets that self-intersect, packing failures). Keep a
   second perspective — you often catch what Claude misses.

2. **Own the verification math.** Implement, as a **self-contained module behind the `FabricationReport`
   contract** (spec §6), with thorough tests:
   - `thicken_to_solids(shells, wall_mm)` — offset open surfaces to closed solids; on a failed/flipped
     offset (the real `offset parts: 0` case) retry the opposite direction, else flag un-thickenable
     with a reason.
   - `validate(parts) → list[PartResult]` — closed / manifold / solid / valid, returning `valid/total`
     (the `16/19` case) + the *why* per failure.
   - `score_orientations(part) → list[OrientationCandidate]` — flat-outer-face vs upright-edge-on-bed,
     scored by support volume + bed stability + show-face quality.
   - `pack(parts, unit) → PackingResult` — bin-pack onto 250×250 print plates / 12×12 laser sheets,
     centered, multi-unit, report efficiency + unplaced.

**Constraints:** code strictly to the `FabricationReport` dataclasses (don't invent a parallel data
model); pure functions where possible; deterministic; thorough unit tests including degenerate inputs;
keep the existing suite green; work on your own branch and hand back a PR. Defaults from the real runs:
wall `0.66 mm` (arch) / `1.2–2.4 mm` (FDM), plate `250×250 mm`, laser sheet `12×12 in`, join-tol sweep
`0.01/0.05`.

Claude builds the pipeline + UI + agent that *call* your functions; the `FabricationReport` contract is
the seam between you — don't cross it.
