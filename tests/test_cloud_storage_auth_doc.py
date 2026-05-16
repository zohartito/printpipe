from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = REPO_ROOT / "docs" / "cloud" / "storage_auth.md"


def test_cloud_storage_auth_doc_covers_future_storage_and_auth_boundaries() -> None:
    assert DOC_PATH.exists()

    content = DOC_PATH.read_text(encoding="utf-8")
    lower_content = content.lower()

    for expected in (
        "auth and storage are not implemented now",
        "private repo",
        "local-first",
        "uploaded references",
        "generated meshes",
        "3mf",
        "reports",
        "logs",
        "deletion",
        "retention",
        "signed urls",
        "local equivalent",
        "user ownership",
        "privacy",
    ):
        assert expected in lower_content
