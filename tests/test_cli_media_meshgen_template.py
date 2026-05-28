from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from printpipe.cli import build_parser, main


def test_media_meshgen_template_parser_accepts_output_path(tmp_path: Path):
    parser = build_parser()
    output_path = tmp_path / "media_adapter.py"

    args = parser.parse_args(["media-meshgen-template", "--output", str(output_path)])

    assert args.command == "media-meshgen-template"
    assert args.output == output_path


def test_media_meshgen_template_prints_protocol_script(capsys):
    exit_code = main(["media-meshgen-template"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "PrintPipe media meshgen adapter template" in captured.out
    assert "parser.add_argument(\"--source\"" in captured.out
    assert "parser.add_argument(\"--output\"" in captured.out
    assert "parser.add_argument(\"--output-format\"" in captured.out
    assert "print(json.dumps({\"output_path\": str(args.output)}))" in captured.out


def test_media_meshgen_template_writes_executable_stub(tmp_path: Path, capsys):
    output_path = tmp_path / "adapters" / "media_meshgen_adapter.py"

    exit_code = main(["media-meshgen-template", "--output", str(output_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert output_path.exists()
    assert os.access(output_path, os.X_OK)
    assert f"export PRINTPIPE_MEDIA_MESHGEN_COMMAND={output_path}" in captured.out

    result = subprocess.run(
        [
            sys.executable,
            str(output_path),
            "--input-kind",
            "image",
            "--source",
            str(tmp_path / "reference.png"),
            "--output",
            str(tmp_path / "mesh.stl"),
            "--output-format",
            "stl",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "Replace generate_mesh() with a real image/GIF/video-to-mesh call" in result.stderr
