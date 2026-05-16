from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = REPO_ROOT / "docs" / "cloud" / "meshgen_decision.md"


def test_hosted_meshgen_decision_doc_covers_current_decision_and_gates() -> None:
    assert DOC_PATH.exists()

    content = DOC_PATH.read_text(encoding="utf-8").lower()

    for expected in (
        "# hosted meshgen decision",
        "## decision",
        "## local-only default",
        "## when hosted mesh generation is needed",
        "## gates before hosted meshgen",
        "## evaluation trigger after local dogfood/beta",
        "not yet; evaluate after local dogfood/beta",
        "local pipeline works first",
        "gpu/provider cost",
        "privacy/ip",
        "queue latency",
        "beta evidence",
        "local-only remains enough",
        "hosted mesh generation is needed when",
    ):
        assert expected in content
