"""The camera-case recipe authors dimension provenance, and the assumed
fit-critical caliper-TODO dims hold the build out of "ready to print".

Loads the example module by file path (cwd-independent) so importing it does not
run the pipeline (main() is guarded by ``if __name__ == "__main__"``).
"""

from __future__ import annotations

import importlib.util
from dataclasses import replace
from pathlib import Path

from printpipe.fabrication import (
    ExportResult,
    FabricationReport,
    FabricationSettings,
    PartResult,
    Provenance,
    Status,
    Target,
    check_fit,
)

RECIPE_PATH = (
    Path(__file__).resolve().parent.parent
    / "examples"
    / "pi_zero_2w_imx477_camera_case.py"
)


def _load_recipe():
    spec = importlib.util.spec_from_file_location("camera_case_recipe", RECIPE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _report(*, dimensions, printability) -> FabricationReport:
    return FabricationReport(
        units="mm",
        tolerance_mm=0.01,
        wall_thickness_mm=2.4,
        target=Target.PRINT,
        dimensions=dimensions,
        parts=[PartResult("body", 100, None, solid=True, valid=True)],
        valid_solids="1 / 1",
        printability=printability,
        orientation=None,
        packing=None,
        exports=ExportResult(),
        agent_summary="",
    )


def test_recipe_exposes_dimension_provenance() -> None:
    recipe = _load_recipe()
    by_name = {dim.name: dim for dim in recipe.DIMENSIONS}

    assert by_name["board_length_mm"].provenance is Provenance.DATASHEET
    assumed_fit_critical = {
        dim.name
        for dim in recipe.DIMENSIONS
        if dim.provenance is Provenance.ASSUMED and dim.fit_critical
    }
    assert assumed_fit_critical == {
        "stack_height_mm",
        "microsd_offset_mm",
        "lens_length_mm",
        "arducam_bracket_footprint_mm",
    }


def test_recipe_fit_context_passes_checks_but_flags_assumed_stack() -> None:
    recipe = _load_recipe()
    checks = check_fit(recipe.fit_context(), settings=FabricationSettings())

    # No hard failures for this (geometrically consistent) mockup.
    assert not any(check.status is Status.FAIL for check in checks)
    # The stack-height check leans on the ASSUMED stack_height_mm -> amber FLAG.
    stack_check = next(
        check for check in checks if check.depends_on_assumed_dim == "stack_height_mm"
    )
    assert stack_check.status is Status.FLAG


def test_recipe_assumed_fit_critical_dims_block_ready_to_print() -> None:
    recipe = _load_recipe()

    # As authored: assumed fit-critical caliper-TODO dims -> NOT ready to print.
    blocked = _report(dimensions=recipe.DIMENSIONS, printability=[])
    assert blocked.ready_to_print is False

    # Ground every dimension (caliper/datasheet) -> the gate clears.
    grounded_dims = [replace(dim, provenance=Provenance.MEASURED) for dim in recipe.DIMENSIONS]
    grounded = _report(dimensions=grounded_dims, printability=[])
    assert grounded.ready_to_print is True
