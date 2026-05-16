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
        "## artifacts to inspect",
        "## gates and pass/fail criteria",
        "## physical steps still required",
        "has not been physically printed by printpipe",
        "mesh repair",
        "bed fit",
        "support/cantilever",
        "slice estimate",
        "flex coupon first",
        "physical print outcome",
        "pass:",
        "fail:",
    ):
        assert expected in content
