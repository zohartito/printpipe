from __future__ import annotations

import json
import struct
import sys
import zlib
from pathlib import Path

from printpipe.cli import build_parser, main


def test_media_meshgen_heightfield_parser_accepts_adapter_protocol(tmp_path: Path):
    parser = build_parser()
    source = tmp_path / "reference.png"
    output = tmp_path / "heightfield.stl"

    args = parser.parse_args(
        [
            "media-meshgen-heightfield",
            "--input-kind",
            "image",
            "--source",
            str(source),
            "--reference-image",
            str(source),
            "--output",
            str(output),
            "--output-format",
            "stl",
            "--target-use",
            "3d_printing",
            "--quality",
            "smoke",
            "--prompt",
            "low relief slipper sole",
        ]
    )

    assert args.command == "media-meshgen-heightfield"
    assert args.input_kind == "image"
    assert args.source == [source]
    assert args.reference_image == [source]
    assert args.output == output
    assert args.output_format == "stl"
    assert args.prompt == "low relief slipper sole"


def test_media_meshgen_heightfield_writes_real_stl_from_png(
    tmp_path: Path,
    capsys,
):
    source = tmp_path / "reference.png"
    output = tmp_path / "heightfield.stl"
    _write_grayscale_png(
        source,
        width=3,
        height=2,
        rows=[
            [0, 64, 128],
            [192, 224, 255],
        ],
    )

    exit_code = main(
        [
            "media-meshgen-heightfield",
            "--input-kind",
            "image",
            "--source",
            str(source),
            "--output",
            str(output),
            "--output-format",
            "stl",
            "--max-grid",
            "8",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    text = output.read_text(encoding="ascii")
    assert exit_code == 0
    assert payload == {"output_path": str(output)}
    assert text.startswith("solid printpipe_heightfield")
    assert "facet normal" in text
    assert "endsolid printpipe_heightfield" in text


def test_media_meshgen_smoke_can_use_builtin_heightfield_command(
    tmp_path: Path,
    capsys,
):
    source = tmp_path / "reference.png"
    runs_dir = tmp_path / "smoke-runs"
    _write_grayscale_png(
        source,
        width=2,
        height=2,
        rows=[
            [0, 255],
            [255, 0],
        ],
    )

    exit_code = main(
        [
            "media-meshgen-smoke",
            str(source),
            "--command",
            f"{sys.executable} -m printpipe.cli media-meshgen-heightfield",
            "--runs-dir",
            str(runs_dir),
        ]
    )

    captured = capsys.readouterr()
    run_root = next(runs_dir.iterdir())
    payload = json.loads((run_root / "20_meshgen" / "smoke.json").read_text())
    assert exit_code == 0
    assert "media meshgen smoke: succeeded" in captured.out
    assert payload["status"] == "succeeded"
    assert payload["provider_id"] == "media_command"
    assert payload["output_path"] == "20_meshgen/media_command.stl"
    assert (run_root / "20_meshgen" / "media_command.stl").exists()


def _write_grayscale_png(path: Path, *, width: int, height: int, rows: list[list[int]]) -> None:
    raw = b"".join(bytes([0, *row]) for row in rows)
    chunks = [
        _png_chunk(
            b"IHDR",
            struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0),
        ),
        _png_chunk(b"IDAT", zlib.compress(raw)),
        _png_chunk(b"IEND", b""),
    ]
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"".join(chunks))


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )
