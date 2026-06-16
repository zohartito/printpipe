"""Dependency-light tests for the 7 fabrication fit checks.

No trimesh / numpy: every FitContext is built from plain numbers. Each of the 7
checks gets a PASS case and a FAIL case, plus one test for the assumed-dimension
amber downgrade.
"""

from __future__ import annotations

from printpipe.fabrication.pipeline import (
    FabricationSettings,
    FitContext,
    check_fit,
)
from printpipe.fabrication.report import Dimension, Provenance, Status


SETTINGS = FabricationSettings(flag_margin_mm=0.5)


def _base_context(**overrides) -> FitContext:
    """A camera-case-like context where all 7 checks comfortably PASS.

    Mirrors the handycam recipe scalars: inner 116x48, total height 55, lens at
    v=30 aligned with the camera, a tripod boss cleared by tall standoffs, etc.
    Individual tests override single fields to force a FAIL.
    """

    defaults = dict(
        board_length_mm=114.0,
        board_width_mm=46.0,
        inner_length_mm=116.0,
        inner_width_mm=48.0,
        internal_height_mm=52.0,
        total_height_mm=55.0,
        clearance_mm=1.0,
        wall_mm=2.4,
        floor_mm=3.0,
        standoff_height_mm=12.0,  # tall enough to clear an 9mm boss + clearance
        boss_dia_mm=14.0,
        boss_height_mm=9.0,
        boss_xy=(22.0, 0.0),
        cutouts=[
            {"face": "-y", "u_mm": -45.5, "z_center_mm": 16.0, "width_mm": 14.0, "height_mm": 12.0},
        ],
        lens={"v_mm": 30.0, "length_mm": 44.0},
        camera={"v_center_mm": 30.0, "post_len_mm": 44.0},
        floor_cutouts=[{"x_mm": 22.0, "y_mm": 0.0, "size_x_mm": 20.0, "size_y_mm": 18.0}],
        bracket_footprint_mm=(16.0, 14.0),
        mount_holes_xy=[(4.0, 11.5), (4.0, -11.5), (-54.0, 11.5), (-54.0, -11.5)],
        grip={"mount_span_mm": 110.0, "mount_hole_dia_mm": 4.0},
        body_grip_holes={"u_positions": [-55.0, 55.0], "diameter_mm": 3.4},
        dimensions=[],
    )
    defaults.update(overrides)
    return FitContext(**defaults)


# --------------------------------------------------------------------------- #
# (1) board <-> shell XY clearance
# --------------------------------------------------------------------------- #
def test_board_shell_clearance_pass():
    checks = check_fit(_base_context(), settings=SETTINGS)
    check = checks[0]
    assert check.name == "clearance"
    assert check.status == Status.PASS


def test_board_shell_clearance_fail_board_too_big():
    ctx = _base_context(board_length_mm=130.0)  # board > inner 116 -> negative gap
    checks = check_fit(ctx, settings=SETTINGS)
    check = checks[0]
    assert check.name == "clearance"
    assert check.status == Status.FAIL


# --------------------------------------------------------------------------- #
# (2) internal height vs stack
# --------------------------------------------------------------------------- #
def test_stack_height_pass():
    ctx = _base_context(dimensions=[Dimension("stack_height_mm", 40.0, Provenance.MEASURED)])
    checks = check_fit(ctx, settings=SETTINGS)
    check = checks[1]
    assert check.name == "clearance"
    assert check.status == Status.PASS


def test_stack_height_fail_stack_too_tall():
    ctx = _base_context(
        internal_height_mm=52.0,
        dimensions=[Dimension("stack_height_mm", 60.0, Provenance.MEASURED)],
    )
    checks = check_fit(ctx, settings=SETTINGS)
    check = checks[1]
    assert check.name == "clearance"
    assert check.status == Status.FAIL


# --------------------------------------------------------------------------- #
# (3) standoff <-> tripod boss
# --------------------------------------------------------------------------- #
def test_standoff_boss_pass():
    checks = check_fit(_base_context(), settings=SETTINGS)
    check = checks[2]
    assert check.name == "interference"
    assert check.status == Status.PASS


def test_standoff_boss_fail_standoff_too_short():
    ctx = _base_context(standoff_height_mm=4.0)  # below 9mm boss -> collision
    checks = check_fit(ctx, settings=SETTINGS)
    check = checks[2]
    assert check.name == "interference"
    assert check.status == Status.FAIL


# --------------------------------------------------------------------------- #
# (4) cutout within wall bounds
# --------------------------------------------------------------------------- #
def test_cutout_pass():
    checks = check_fit(_base_context(), settings=SETTINGS)
    # cutouts start at index 3 (one cutout in the baseline).
    check = checks[3]
    assert check.name == "interference"
    assert check.status == Status.PASS


def test_cutout_fail_off_edge():
    # u=-110 with width 14 on a -y wall: |u|+w/2 = 117 > half-length 58.
    ctx = _base_context(
        cutouts=[{"face": "-y", "u_mm": -110.0, "z_center_mm": 16.0, "width_mm": 14.0, "height_mm": 12.0}]
    )
    checks = check_fit(ctx, settings=SETTINGS)
    check = checks[3]
    assert check.name == "interference"
    assert check.status == Status.FAIL


# --------------------------------------------------------------------------- #
# (5) lens axis + length
# --------------------------------------------------------------------------- #
def test_lens_pass():
    checks = check_fit(_base_context(), settings=SETTINGS)
    check = checks[4]
    assert check.name == "clearance"
    assert check.status == Status.PASS


def test_lens_fail_axis_misaligned():
    ctx = _base_context(lens={"v_mm": 20.0, "length_mm": 44.0})  # 10mm off camera axis
    checks = check_fit(ctx, settings=SETTINGS)
    check = checks[4]
    assert check.name == "clearance"
    assert check.status == Status.FAIL


# --------------------------------------------------------------------------- #
# (6) floor cutout <-> bracket
# --------------------------------------------------------------------------- #
def test_floor_cutout_pass():
    checks = check_fit(_base_context(), settings=SETTINGS)
    check = checks[5]
    assert check.name == "interference"
    assert check.status == Status.PASS


def test_floor_cutout_fail_bracket_too_big():
    ctx = _base_context(bracket_footprint_mm=(30.0, 14.0))  # 30 > cutout 20
    checks = check_fit(ctx, settings=SETTINGS)
    check = checks[5]
    assert check.name == "interference"
    assert check.status == Status.FAIL


# --------------------------------------------------------------------------- #
# (7) grip <-> body registration
# --------------------------------------------------------------------------- #
def test_grip_pass():
    checks = check_fit(_base_context(), settings=SETTINGS)
    check = checks[6]
    assert check.name == "interference"
    assert check.status == Status.PASS


def test_grip_fail_span_mismatch():
    ctx = _base_context(
        grip={"mount_span_mm": 90.0, "mount_hole_dia_mm": 4.0},  # body span is 110
    )
    checks = check_fit(ctx, settings=SETTINGS)
    check = checks[6]
    assert check.name == "interference"
    assert check.status == Status.FAIL


# --------------------------------------------------------------------------- #
# Assumed-dimension amber downgrade (PASS -> FLAG)
# --------------------------------------------------------------------------- #
def test_assumed_dim_downgrades_pass_to_flag():
    # Board<->shell clearance would PASS, but inner_length_mm is ASSUMED, so it
    # must downgrade to FLAG and record the governing dimension.
    ctx = _base_context(
        dimensions=[
            Dimension("inner_length_mm", 116.0, Provenance.ASSUMED, fit_critical=True),
        ]
    )
    checks = check_fit(ctx, settings=SETTINGS)
    check = checks[0]
    assert check.status == Status.FLAG
    assert check.depends_on_assumed_dim == "inner_length_mm"


def test_assumed_dim_does_not_rescue_fail():
    # A genuine FAIL stays FAIL even when the governing dimension is assumed.
    ctx = _base_context(
        board_length_mm=130.0,
        dimensions=[
            Dimension("inner_length_mm", 116.0, Provenance.ASSUMED, fit_critical=True),
        ],
    )
    checks = check_fit(ctx, settings=SETTINGS)
    check = checks[0]
    assert check.status == Status.FAIL
    assert check.depends_on_assumed_dim == "inner_length_mm"
