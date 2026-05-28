from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = REPO_ROOT / "docs" / "beta" / "slipper_dogfood.md"


def test_slipper_dogfood_doc_covers_validation_gates() -> None:
    assert DOC_PATH.exists()

    content = DOC_PATH.read_text(encoding="utf-8").lower()

    for expected in (
        "# slipper dogfood validation",
        "## proof-of-concept path",
        "## what to run",
        "## current printpipe-owned software evidence",
        "## artifacts to inspect",
        "## gates and pass/fail criteria",
        "## physical steps still required",
        "has not been physically printed by printpipe",
        "20260528-042826-slipper-size11-v2c-wide-upper-textured",
        "sunlu tpu 90a",
        "support_style=snug",
        "boundary edges went from 364200 to 0",
        "slice gate: skipped",
        "mesh repair",
        "bed fit",
        "support/cantilever",
        "slice estimate",
        "flex coupon first",
        "physical evidence packet",
        "photo artifact",
        "filament drying",
        "layer bonding",
        "flex recovery",
        "physical print outcome",
        "pass:",
        "fail:",
    ):
        assert expected in content


def test_slipper_dogfood_doc_requires_explicit_physical_outcome() -> None:
    content = DOC_PATH.read_text(encoding="utf-8").lower()

    assert '--print-status "<passed|failed|partial>"' in content
    assert "--print-status passed" not in content
