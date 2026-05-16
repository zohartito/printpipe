from __future__ import annotations

from pathlib import Path

from printpipe.cli import main


def test_version_prints_package_version(capsys):
    exit_code = main(["--version"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "printpipe 0.1.0" in captured.out


def test_init_run_requires_existing_input(tmp_path: Path, capsys):
    source = tmp_path / "reference.png"
    source.write_bytes(b"not really an image yet")
    runs_dir = tmp_path / "runs"

    exit_code = main(["init-run", str(source), "--runs-dir", str(runs_dir)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert runs_dir.exists()
    assert "run root:" in captured.out
    assert str(source.resolve()) in captured.out

