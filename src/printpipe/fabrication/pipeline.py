"""Claude-owned fabrication pipeline orchestration.

This module assembles a :class:`FabricationReport` from Codex's deterministic
geometry-verification functions plus Claude's product-fit reasoning. It is the
correctness-critical seam between "is the geometry a valid solid?" (Codex) and
"does this product actually fit together / fit its parts?" (Claude).

Hard constraint: everything here imports and runs WITHOUT trimesh/numpy. The
fit checks consume plain scalars via :class:`FitContext`; only ``fabricate``'s
calls into the geometry functions touch trimesh, and those are guarded so their
absence degrades orientation/packing to ``None`` instead of crashing.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Optional

from printpipe.fabrication.report import (
    Check,
    Dimension,
    ExportResult,
    FabricationReport,
    OrientationCandidate,
    PackingResult,
    Provenance,
    Status,
    Target,
)
from printpipe.fabrication.verification import (
    pack,
    score_orientations,
    thicken_to_solids,
    validate,
)

# Default M3 screw shank diameter, used in the grip-registration check (#7) to
# confirm a body clearance hole actually lets the screw pass through.
_M3_SCREW_DIA_MM = 3.0


# --------------------------------------------------------------------------- #
# Dependency-light settings + input dataclasses
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class FabricationSettings:
    """Knobs for one fabrication pass. Frozen so a pass can't mutate them."""

    target: Target = Target.PRINT
    wall_thickness_mm: float = 2.4
    tolerance_mm: float = 0.01
    flag_margin_mm: float = 0.5
    pack_unit: str = "250x250 plate"


@dataclass(frozen=True)
class FitContext:
    """Plain-scalar fit inputs for ``check_fit``.

    Deliberately carries NO ``EnclosureSpec`` (which would drag in trimesh).
    Every field a check needs is a scalar / list of dicts. Optional fields let
    individual checks self-skip (emitting a PASS "not applicable: ...") when the
    corresponding feature is absent from the product.
    """

    # Shell + board footprint (check 1).
    board_length_mm: float
    board_width_mm: float
    inner_length_mm: float
    inner_width_mm: float

    # Heights (checks 2, 4).
    internal_height_mm: float
    total_height_mm: float

    # Global build params.
    clearance_mm: float = 0.0
    wall_mm: float = 0.0
    floor_mm: float = 0.0

    # Standoffs vs tripod boss (check 3).
    standoff_height_mm: float = 0.0
    boss_dia_mm: Optional[float] = None
    boss_height_mm: Optional[float] = None
    boss_xy: Optional[tuple[float, float]] = None

    # Side cutouts (check 4): list of {face,u_mm,z_center_mm,width_mm,height_mm}.
    cutouts: list[dict] = field(default_factory=list)

    # Lens + camera alignment (check 5).
    lens: Optional[dict] = None  # {v_mm, length_mm}
    camera: Optional[dict] = None  # {v_center_mm, post_len_mm}

    # Floor cutout vs bracket (check 6).
    floor_cutouts: list[dict] = field(default_factory=list)
    bracket_footprint_mm: Optional[tuple[float, float]] = None  # (w, d)
    mount_holes_xy: list[tuple[float, float]] = field(default_factory=list)

    # Grip vs body registration (check 7).
    grip: Optional[dict] = None  # {mount_span_mm, mount_hole_dia_mm}
    body_grip_holes: Optional[dict] = None  # {u_positions: [...], diameter_mm}

    # Dimension provenance/criticality lookup for the amber-downgrade rule.
    dimensions: list[Dimension] = field(default_factory=list)


@dataclass
class FabricationModel:
    """A product staged for fabrication.

    ``parts`` is whatever Codex's verification functions accept: trimesh meshes,
    ``{"vertices": ..., "faces": ...}`` mappings, or already-built ``PartResult``
    objects (which thicken/validate pass straight through). ``fit`` is the
    dependency-light fit context; ``dimensions`` is the dimension table surfaced
    in the report and used by ``check_fit`` for the assumed-dim downgrade.
    """

    parts: list
    fit: Optional[FitContext]
    dimensions: list[Dimension]


# --------------------------------------------------------------------------- #
# Fit checks (dependency-light)
# --------------------------------------------------------------------------- #
def check_fit(ctx: FitContext, *, settings: FabricationSettings) -> list[Check]:
    """Run the 7 product-fit checks against plain scalars.

    Each check yields one (or, for per-cutout checks, several) ``Check`` with a
    ``name`` of either ``"clearance"`` or ``"interference"``. After building each
    check, the assumed-dim rule may stamp ``depends_on_assumed_dim`` and
    downgrade a PASS to FLAG (a FAIL stays a FAIL).
    """

    flag = settings.flag_margin_mm
    dim_index = {dim.name: dim for dim in ctx.dimensions}
    checks: list[Check] = []

    # (1) board <-> shell XY clearance --------------------------------------- #
    gap_len = (ctx.inner_length_mm - ctx.board_length_mm) / 2.0
    gap_wid = (ctx.inner_width_mm - ctx.board_width_mm) / 2.0
    worst_gap = min(gap_len, gap_wid)
    if worst_gap < 0:
        status = Status.FAIL
        detail = (
            f"board overruns shell: min XY gap {worst_gap:.3f} mm "
            f"(len gap {gap_len:.3f}, width gap {gap_wid:.3f})"
        )
    elif worst_gap < flag:
        status = Status.FLAG
        detail = f"tight board<->shell gap {worst_gap:.3f} mm < flag margin {flag:.3f} mm"
    else:
        status = Status.PASS
        detail = (
            f"board fits shell: min XY gap {worst_gap:.3f} mm "
            f"(len {gap_len:.3f}, width {gap_wid:.3f})"
        )
    checks.append(
        _with_assumption(
            Check("clearance", status, detail),
            dim_index,
            ("inner_length_mm", "inner_width_mm", "board_length_mm", "board_width_mm"),
        )
    )

    # (2) internal height vs stack ------------------------------------------- #
    stack_dim = dim_index.get("stack_height_mm")
    if stack_dim is None:
        checks.append(
            Check(
                "clearance",
                Status.PASS,
                "not applicable: no 'stack_height_mm' dimension provided",
            )
        )
    else:
        stack_height = float(stack_dim.value_mm)
        head_gap = ctx.internal_height_mm - (stack_height + ctx.clearance_mm)
        if head_gap < 0:
            status = Status.FAIL
            detail = (
                f"stack too tall: internal height {ctx.internal_height_mm:.3f} mm vs "
                f"stack {stack_height:.3f} + clearance {ctx.clearance_mm:.3f} "
                f"(head gap {head_gap:.3f} mm)"
            )
        elif head_gap < flag:
            status = Status.FLAG
            detail = f"tight headroom {head_gap:.3f} mm < flag margin {flag:.3f} mm"
        else:
            status = Status.PASS
            detail = (
                f"stack fits: head gap {head_gap:.3f} mm "
                f"(internal {ctx.internal_height_mm:.3f} vs stack {stack_height:.3f} "
                f"+ clearance {ctx.clearance_mm:.3f})"
            )
        checks.append(
            _with_assumption(
                Check("clearance", status, detail),
                dim_index,
                ("stack_height_mm", "internal_height_mm"),
            )
        )

    # (3) standoff <-> tripod boss ------------------------------------------- #
    if ctx.boss_height_mm is None:
        checks.append(
            Check(
                "interference",
                Status.PASS,
                "not applicable: no tripod boss in this product",
            )
        )
    else:
        boss_h = float(ctx.boss_height_mm)
        # The Pi must clear the boss: standoffs must lift the board ABOVE the
        # boss (+ clearance). Equal/below heights means the boss collides.
        margin = ctx.standoff_height_mm - (boss_h + ctx.clearance_mm)
        if margin <= 0:
            status = Status.FAIL
            detail = (
                f"standoffs do not clear tripod boss: standoff {ctx.standoff_height_mm:.3f} mm "
                f"vs boss {boss_h:.3f} + clearance {ctx.clearance_mm:.3f} (margin {margin:.3f} mm)"
            )
        elif margin < flag:
            status = Status.FLAG
            detail = f"tight standoff/boss clearance {margin:.3f} mm < flag margin {flag:.3f} mm"
        else:
            status = Status.PASS
            detail = (
                f"standoffs clear tripod boss: margin {margin:.3f} mm "
                f"(standoff {ctx.standoff_height_mm:.3f} vs boss {boss_h:.3f} "
                f"+ clearance {ctx.clearance_mm:.3f})"
            )
        checks.append(
            _with_assumption(
                Check("interference", status, detail),
                dim_index,
                ("standoff_height_mm", "boss_height_mm"),
            )
        )

    # (4) cutouts within wall bounds (one per cutout) ------------------------ #
    if not ctx.cutouts:
        checks.append(
            Check("interference", Status.PASS, "not applicable: no wall cutouts")
        )
    else:
        for index, cut in enumerate(ctx.cutouts):
            checks.append(
                _with_assumption(
                    _check_cutout(cut, index, ctx, flag),
                    dim_index,
                    ("inner_length_mm", "inner_width_mm", "total_height_mm"),
                )
            )

    # (5) lens axis + length ------------------------------------------------- #
    if ctx.lens is None or ctx.camera is None:
        checks.append(
            Check(
                "clearance",
                Status.PASS,
                "not applicable: no lens/camera pair provided",
            )
        )
    else:
        lens_v = float(ctx.lens["v_mm"])
        lens_len = float(ctx.lens["length_mm"])
        cam_v = float(ctx.camera["v_center_mm"])
        axis_offset = abs(lens_v - cam_v)
        length_over = lens_len - ctx.inner_length_mm
        if axis_offset > flag or length_over > 0:
            status = Status.FAIL
            reasons = []
            if axis_offset > flag:
                reasons.append(
                    f"lens axis off camera by {axis_offset:.3f} mm > flag {flag:.3f}"
                )
            if length_over > 0:
                reasons.append(
                    f"lens length {lens_len:.3f} mm exceeds inner length "
                    f"{ctx.inner_length_mm:.3f} by {length_over:.3f}"
                )
            detail = "; ".join(reasons)
        elif axis_offset > 0:
            status = Status.FLAG
            detail = (
                f"small lens-axis offset {axis_offset:.3f} mm (<= flag {flag:.3f}); "
                f"lens length {lens_len:.3f} fits inner {ctx.inner_length_mm:.3f}"
            )
        else:
            status = Status.PASS
            detail = (
                f"lens aligned (offset {axis_offset:.3f} mm) and fits "
                f"(length {lens_len:.3f} <= inner {ctx.inner_length_mm:.3f})"
            )
        checks.append(
            _with_assumption(
                Check("clearance", status, detail),
                dim_index,
                ("inner_length_mm",),
            )
        )

    # (6) floor cutout <-> bracket ------------------------------------------- #
    if not ctx.floor_cutouts or ctx.bracket_footprint_mm is None:
        checks.append(
            Check(
                "interference",
                Status.PASS,
                "not applicable: no floor cutout / bracket footprint provided",
            )
        )
    else:
        checks.append(
            _with_assumption(
                _check_floor_cutout(ctx, flag),
                dim_index,
                ("inner_length_mm", "inner_width_mm"),
            )
        )

    # (7) grip <-> body registration ----------------------------------------- #
    if ctx.grip is None or ctx.body_grip_holes is None:
        checks.append(
            Check("interference", Status.PASS, "not applicable: no grip in this product")
        )
    else:
        checks.append(
            _with_assumption(
                _check_grip(ctx, flag),
                dim_index,
                ("mount_span_mm",),
            )
        )

    return checks


def _check_cutout(cut: dict, index: int, ctx: FitContext, flag: float) -> Check:
    """Check one wall cutout stays within its wall's bounds (check 4)."""

    face = str(cut["face"])
    u = float(cut["u_mm"])
    z_center = float(cut["z_center_mm"])
    width = float(cut["width_mm"])
    height = float(cut["height_mm"])

    # +/-y faces run along the case length; +/-x faces run along the width.
    if face in ("+y", "-y"):
        half_len = ctx.inner_length_mm / 2.0
        face_axis = "length"
    else:
        half_len = ctx.inner_width_mm / 2.0
        face_axis = "width"

    u_over = (abs(u) + width / 2.0) - half_len
    z_low = z_center - height / 2.0
    z_high = z_center + height / 2.0
    z_low_over = -z_low  # >0 means the opening dips below the floor exterior (z=0)
    z_high_over = z_high - ctx.total_height_mm

    worst_over = max(u_over, z_low_over, z_high_over)
    label = f"cutout[{index}] '{face}'"
    if worst_over > 0:
        reasons = []
        if u_over > 0:
            reasons.append(
                f"runs off {face_axis} edge by {u_over:.3f} mm "
                f"(|u| {abs(u):.3f} + half-width {width / 2.0:.3f} > half-face {half_len:.3f})"
            )
        if z_low_over > 0:
            reasons.append(f"dips {z_low_over:.3f} mm below the floor (z={z_low:.3f})")
        if z_high_over > 0:
            reasons.append(
                f"exceeds top by {z_high_over:.3f} mm "
                f"(z={z_high:.3f} > total height {ctx.total_height_mm:.3f})"
            )
        return Check("interference", Status.FAIL, f"{label}: " + "; ".join(reasons))
    if -worst_over < flag:
        return Check(
            "interference",
            Status.FLAG,
            f"{label}: within bounds but tight (closest margin {-worst_over:.3f} mm < flag {flag:.3f})",
        )
    return Check(
        "interference",
        Status.PASS,
        f"{label}: within wall bounds (closest margin {-worst_over:.3f} mm)",
    )


def _check_floor_cutout(ctx: FitContext, flag: float) -> Check:
    """Check the bracket fits the floor cutout, which fits the floor interior
    and avoids mount-hole posts (check 6)."""

    cut = ctx.floor_cutouts[0]
    cx = float(cut["x_mm"])
    cy = float(cut["y_mm"])
    sx = float(cut["size_x_mm"])
    sy = float(cut["size_y_mm"])
    bracket_w, bracket_d = (float(value) for value in ctx.bracket_footprint_mm)

    # Bracket must fit inside the cutout.
    bracket_over_x = bracket_w - sx
    bracket_over_y = bracket_d - sy

    # Cutout must sit inside the floor interior (the inner footprint).
    half_inner_x = ctx.inner_length_mm / 2.0
    half_inner_y = ctx.inner_width_mm / 2.0
    cut_edge_x_over = (abs(cx) + sx / 2.0) - half_inner_x
    cut_edge_y_over = (abs(cy) + sy / 2.0) - half_inner_y

    # Cutout must not overlap a mount-hole post.
    overlapping = [
        (mx, my)
        for mx, my in ctx.mount_holes_xy
        if abs(float(mx) - cx) <= sx / 2.0 and abs(float(my) - cy) <= sy / 2.0
    ]

    if overlapping:
        return Check(
            "interference",
            Status.FAIL,
            f"floor cutout overlaps mount hole(s) {overlapping}",
        )
    worst_over = max(bracket_over_x, bracket_over_y, cut_edge_x_over, cut_edge_y_over)
    if worst_over > 0:
        reasons = []
        if bracket_over_x > 0 or bracket_over_y > 0:
            reasons.append(
                f"bracket {bracket_w:.3f}x{bracket_d:.3f} exceeds cutout {sx:.3f}x{sy:.3f}"
            )
        if cut_edge_x_over > 0 or cut_edge_y_over > 0:
            reasons.append("cutout extends past the floor interior")
        return Check("interference", Status.FAIL, "floor cutout: " + "; ".join(reasons))
    if -worst_over < flag:
        return Check(
            "interference",
            Status.FLAG,
            f"floor cutout: bracket fits but tight (closest margin {-worst_over:.3f} mm < flag {flag:.3f})",
        )
    return Check(
        "interference",
        Status.PASS,
        f"floor cutout clears bracket and floor interior (closest margin {-worst_over:.3f} mm)",
    )


def _check_grip(ctx: FitContext, flag: float) -> Check:
    """Check grip leg spacing registers with the body holes, and the body hole
    clears the screw (check 7)."""

    grip_span = float(ctx.grip["mount_span_mm"])
    insert_pocket_dia = float(ctx.grip["mount_hole_dia_mm"])
    u_positions = [float(value) for value in ctx.body_grip_holes["u_positions"]]
    body_hole_dia = float(ctx.body_grip_holes["diameter_mm"])
    body_span = max(u_positions) - min(u_positions)

    span_mismatch = abs(grip_span - body_span)
    # The grip's mount_hole_dia is a heat-set INSERT pocket; the body hole must
    # clear the screw shank, not the pocket. Failing that, the screw can't pass.
    screw_clearance = body_hole_dia - _M3_SCREW_DIA_MM

    # Screw clearance is pass/fail (the body hole either passes the screw or it
    # doesn't); only the leg-span registration drives the tight/FLAG band.
    if span_mismatch > flag or screw_clearance < 0:
        reasons = []
        if span_mismatch > flag:
            reasons.append(
                f"grip span {grip_span:.3f} mm vs body hole span {body_span:.3f} mm "
                f"(mismatch {span_mismatch:.3f} > flag {flag:.3f})"
            )
        if screw_clearance < 0:
            reasons.append(
                f"body hole {body_hole_dia:.3f} mm does not clear M{_M3_SCREW_DIA_MM:g} screw "
                f"(short by {-screw_clearance:.3f} mm)"
            )
        return Check("interference", Status.FAIL, "grip<->body: " + "; ".join(reasons))
    if span_mismatch > 0:
        return Check(
            "interference",
            Status.FLAG,
            f"grip<->body: registers but tight (span mismatch {span_mismatch:.3f} mm "
            f"<= flag {flag:.3f}; screw clearance {screw_clearance:.3f} mm, "
            f"insert pocket {insert_pocket_dia:.3f} mm)",
        )
    return Check(
        "interference",
        Status.PASS,
        f"grip<->body registers: span match (mismatch {span_mismatch:.3f} mm) and "
        f"body hole {body_hole_dia:.3f} mm clears screw (margin {screw_clearance:.3f} mm)",
    )


def _with_assumption(
    check: Check,
    dim_index: dict[str, Dimension],
    dim_names: tuple[str, ...],
) -> Check:
    """Stamp ``depends_on_assumed_dim`` and amber-downgrade a PASS to FLAG when a
    governing dimension is ASSUMED. A FAIL stays a FAIL."""

    assumed = next(
        (
            name
            for name in dim_names
            if name in dim_index and dim_index[name].provenance == Provenance.ASSUMED
        ),
        None,
    )
    if assumed is None:
        return check
    new_status = Status.FLAG if check.status == Status.PASS else check.status
    suffix = f" [leans on assumed dimension '{assumed}']"
    return replace(
        check,
        status=new_status,
        detail=check.detail + suffix,
        depends_on_assumed_dim=assumed,
    )


# --------------------------------------------------------------------------- #
# Pipeline assembly
# --------------------------------------------------------------------------- #
def fabricate(
    model: FabricationModel,
    target: Target,
    settings: FabricationSettings,
) -> FabricationReport:
    """Assemble a :class:`FabricationReport` for ``model`` at ``target``.

    Geometry-touching calls (thicken/validate/orientation/packing) are guarded:
    if trimesh/numpy are missing or a part has no usable extents, orientation and
    packing degrade to ``None`` and the reason is recorded in ``agent_summary``
    instead of crashing the assembly.
    """

    settings = replace(settings, target=target)  # positional target wins
    notes: list[str] = []

    # Thicken + validate. thicken_to_solids offsets open *shells* into solids;
    # a meshless PartResult has nothing to thicken and would be marked
    # un-thickenable, so route those straight to validate (which passes meshless
    # PartResults through verbatim). Mesh-bearing inputs get the full thicken
    # pass. validate is the authoritative solid-validity gate either way. The
    # mesh-bearing branch can touch trimesh, so guard it.
    shells, prebuilt = _split_inputs(model.parts)
    try:
        thickened = thicken_to_solids(shells, settings.wall_thickness_mm) if shells else []
        parts = validate([*thickened, *prebuilt])
    except (ImportError, RuntimeError, ValueError) as exc:
        parts = validate(prebuilt) if prebuilt else []
        notes.append(
            f"geometry verification unavailable for mesh inputs ({exc}); "
            "only pre-built parts validated"
        )

    valid_count = sum(1 for part in parts if part.valid)
    valid_solids = f"{valid_count} / {len(parts)}"

    printability = check_fit(model.fit, settings=settings) if model.fit else []

    orientation = _safe_orientation(parts, notes)
    packing = _safe_packing(parts, settings.pack_unit, notes)

    exports = ExportResult()  # Phase 0 stub: writes no files.

    agent_summary = _agent_summary(
        valid_solids=valid_solids,
        printability=printability,
        dimensions=model.dimensions,
        packing=packing,
        notes=notes,
    )

    return FabricationReport(
        units="mm",
        tolerance_mm=settings.tolerance_mm,
        wall_thickness_mm=settings.wall_thickness_mm,
        target=settings.target,
        dimensions=model.dimensions,
        parts=parts,
        valid_solids=valid_solids,
        printability=printability,
        orientation=orientation,
        packing=packing,
        exports=exports,
        agent_summary=agent_summary,
    )


def _safe_orientation(parts: list, notes: list[str]) -> Optional[OrientationCandidate]:
    """Score orientations for the highest-detail valid part; degrade to None."""

    valid_parts = [part for part in parts if part.valid]
    if not valid_parts:
        notes.append("orientation skipped: no valid solids to orient")
        return None
    representative = max(valid_parts, key=lambda part: part.source_faces)
    try:
        candidates = score_orientations(representative)
    except (ImportError, RuntimeError, ValueError) as exc:
        notes.append(f"orientation unavailable ({exc})")
        return None
    return candidates[0] if candidates else None


def _safe_packing(parts: list, pack_unit: str, notes: list[str]) -> Optional[PackingResult]:
    """Pack parts onto plates/sheets; degrade to None on missing geometry."""

    try:
        return pack(parts, pack_unit)
    except (ImportError, RuntimeError, ValueError) as exc:
        notes.append(f"packing unavailable ({exc})")
        return None


def _split_inputs(raw_parts: list) -> tuple[list, list]:
    """Partition inputs into (shells-to-thicken, pre-built PartResults).

    A pre-built ``PartResult`` carries no mesh, so it routes around
    ``thicken_to_solids`` (which would flag it un-thickenable) and goes straight
    to ``validate`` for pass-through. Everything else (meshes, ``{vertices,
    faces}`` dicts, shells) is a thicken candidate.
    """

    from printpipe.fabrication.report import PartResult

    shells: list = []
    prebuilt: list = []
    for part in raw_parts:
        if isinstance(part, PartResult):
            prebuilt.append(part)
        else:
            shells.append(part)
    return shells, prebuilt


def _agent_summary(
    *,
    valid_solids: str,
    printability: list[Check],
    dimensions: list[Dimension],
    packing: Optional[PackingResult],
    notes: list[str],
) -> str:
    """Build a plain-English rollup for the agent / UI layer."""

    lines: list[str] = [f"Valid solids: {valid_solids}."]

    non_pass = [check for check in printability if check.status != Status.PASS]
    if non_pass:
        lines.append("Fit issues:")
        for check in non_pass:
            lines.append(f"  - [{check.status.value}] {check.name}: {check.detail}")
    elif printability:
        lines.append("All fit checks pass.")

    assumed_critical = [
        dim
        for dim in dimensions
        if dim.provenance == Provenance.ASSUMED and dim.fit_critical
    ]
    if assumed_critical:
        lines.append("Assumed fit-critical dimensions (verify before printing):")
        for dim in assumed_critical:
            lines.append(f"  - {dim.name} = {dim.value_mm} mm (assumed)")

    if packing is not None and packing.unplaced:
        lines.append(f"Unplaced parts in packing: {', '.join(packing.unplaced)}.")

    for note in notes:
        lines.append(f"Note: {note}")

    return "\n".join(lines)
