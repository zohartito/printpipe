"""The watch-folder loop never writes inside the inbox it watches.

launchd's WatchPaths fires on any write in the inbox, so state and report
written there re-ran the watcher every ~10 s forever (2026-10-22: 426k runs on
an empty inbox). Loads the tool by file path, like the other tools/ tests.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

TOOL_PATH = Path(__file__).resolve().parents[1] / "tools" / "watch_3mf_queue.py"


def _load_tool():
    spec = importlib.util.spec_from_file_location("watch_3mf_queue", TOOL_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _snapshot(directory: Path) -> dict[str, int]:
    return {path.name: path.stat().st_mtime_ns for path in directory.iterdir()}


def test_runs_write_nothing_inside_the_watched_inbox(tmp_path, monkeypatch, capsys):
    tool = _load_tool()
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "bad.3mf").write_bytes(b"not a zip")  # invalid: validated, never sliced
    before = _snapshot(inbox)

    # First run processes bad.3mf; the second is the re-fire a write would cause.
    for _ in range(2):
        monkeypatch.setattr(sys, "argv",
                            ["watch_3mf_queue.py", "--inbox", str(inbox), "--no-learning"])
        assert tool.main() == 0
    capsys.readouterr()

    assert _snapshot(inbox) == before
    watch_dir = tmp_path / "inbox-watch"
    state = json.loads((watch_dir / ".watch-state.json").read_text(encoding="utf-8"))
    assert state["bad.3mf"]["valid"] is False
    report = json.loads((watch_dir / "queue-report.latest.json").read_text(encoding="utf-8"))
    assert report["counts"]["new"] == 0  # already processed at this content hash
