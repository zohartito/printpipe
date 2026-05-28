from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TROUBLESHOOTING_DOC = REPO_ROOT / "docs" / "TROUBLESHOOTING.md"


def _read_troubleshooting() -> str:
    assert TROUBLESHOOTING_DOC.exists()
    return TROUBLESHOOTING_DOC.read_text(encoding="utf-8").lower()


def test_troubleshooting_documents_macos_tcc_recovery() -> None:
    content = _read_troubleshooting()

    for expected in (
        "macos desktop and privacy permissions",
        "privacy/tcc",
        "desktop, documents, downloads",
        "wrong first fix",
        "full disk access",
        "terminal",
        "codex",
        "cursor",
        "quit and reopen",
        "printpipe_artifact_paths",
        "printpipe doctor",
    ):
        assert expected in content
