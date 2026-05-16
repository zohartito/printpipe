from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = REPO_ROOT / "docs" / "research" / "wave5_cross_object_orientation_review.md"


def test_wave5_cross_object_orientation_review_doc_covers_required_scope() -> None:
    assert DOC_PATH.exists()

    content = DOC_PATH.read_text(encoding="utf-8").lower()

    for expected in (
        "slipper",
        "figurine",
        "cup/vase",
        "flat bracket",
        "decorative organic",
        "existing stl pipeline",
        "reliable",
        "partial",
        "unsolved",
        "acceptance criteria",
    ):
        assert expected in content
