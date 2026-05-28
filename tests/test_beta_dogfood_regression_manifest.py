from pathlib import Path

from printpipe.beta.regression import load_regression_manifest


MANIFEST_PATH = Path("regressions/dogfood_failures.json")


def test_dogfood_failure_manifest_tracks_wave100_regressions() -> None:
    manifest = load_regression_manifest(MANIFEST_PATH)

    cases = {case.case_id: case for case in manifest.cases}

    assert set(cases) == {
        "dogfood-cup-vase-networkx",
        "dogfood-cup-vase-open-rim-repair",
        "dogfood-flat-bracket-bed-fit-rotation",
    }
    assert all(case.expected.value == "success" for case in cases.values())
    assert (
        cases["dogfood-cup-vase-networkx"].fixture_path.as_posix()
        == "tests/fixtures/objects/cup_vase/cup_vase_open_frustum.stl"
    )
    assert (
        cases["dogfood-flat-bracket-bed-fit-rotation"].fixture_path.as_posix()
        == "tests/fixtures/objects/flat_bracket/flat_bracket.stl"
    )
