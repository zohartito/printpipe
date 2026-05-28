from __future__ import annotations

import json
import sys
from pathlib import Path

from printpipe.cli import build_parser, main


def test_media_meshgen_smoke_parser_accepts_input_command_and_runs_dir(tmp_path: Path):
    parser = build_parser()
    source = tmp_path / "reference.png"
    runs_dir = tmp_path / "smoke-runs"

    args = parser.parse_args(
        [
            "media-meshgen-smoke",
            str(source),
            "--command",
            "media-adapter --fast",
            "--runs-dir",
            str(runs_dir),
            "--output-format",
            "stl",
        ]
    )

    assert args.command == "media-meshgen-smoke"
    assert args.input == source
    assert args.media_command == "media-adapter --fast"
    assert args.runs_dir == runs_dir
    assert args.output_format == "stl"


def test_media_meshgen_smoke_runs_configured_command_and_writes_receipt(
    tmp_path: Path,
    capsys,
):
    source_mesh = (
        Path(__file__).parent
        / "fixtures"
        / "objects"
        / "existing_stl_pipeline"
        / "tiny_tetrahedron.stl"
    )
    fake_adapter = tmp_path / "fake_media_adapter.py"
    fake_adapter.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import argparse",
                "parser = argparse.ArgumentParser()",
                "parser.add_argument('--output', required=True)",
                "args, _ = parser.parse_known_args()",
                f"Path(args.output).write_text(Path({str(source_mesh)!r}).read_text(encoding='ascii'), encoding='ascii')",
                "",
            ]
        ),
        encoding="utf-8",
    )
    source = tmp_path / "reference.png"
    source.write_bytes(b"fake image")
    runs_dir = tmp_path / "smoke-runs"

    exit_code = main(
        [
            "media-meshgen-smoke",
            str(source),
            "--command",
            f"{sys.executable} {fake_adapter}",
            "--runs-dir",
            str(runs_dir),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "media meshgen smoke: succeeded" in captured.out
    assert "provider: media_command" in captured.out
    run_root = next(runs_dir.iterdir())
    payload = json.loads((run_root / "20_meshgen" / "smoke.json").read_text())
    assert payload["status"] == "succeeded"
    assert payload["provider_id"] == "media_command"
    assert payload["output_path"] == "20_meshgen/media_command.stl"
    assert (run_root / "20_meshgen" / "media_command.stl").exists()


def test_media_meshgen_smoke_without_provider_fails_with_setup_action(
    tmp_path: Path,
    capsys,
    monkeypatch,
):
    monkeypatch.delenv("PRINTPIPE_MEDIA_MESHGEN_COMMAND", raising=False)
    monkeypatch.delenv("PRINTPIPE_HUNYUAN3D_COMMAND", raising=False)
    source = tmp_path / "reference.png"
    source.write_bytes(b"fake image")

    exit_code = main(
        [
            "media-meshgen-smoke",
            str(source),
            "--runs-dir",
            str(tmp_path / "smoke-runs"),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "media meshgen smoke: failed" in captured.out
    assert "printpipe media-meshgen-template" in captured.err
    run_root = next((tmp_path / "smoke-runs").iterdir())
    payload = json.loads((run_root / "20_meshgen" / "smoke.json").read_text())
    assert payload["status"] == "failed"
    assert payload["provider_id"] == "media_command"
    assert "PRINTPIPE_MEDIA_MESHGEN_COMMAND" in payload["error"]
