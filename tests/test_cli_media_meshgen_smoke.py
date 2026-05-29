from __future__ import annotations

import json
import sys
from pathlib import Path

from printpipe.cli import build_parser, main
from printpipe.meshgen.smoke import build_media_meshgen_smoke_status


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


def test_media_meshgen_smoke_status_parser_accepts_runs_dir_json_and_strict(
    tmp_path: Path,
):
    parser = build_parser()

    args = parser.parse_args(
        [
            "media-meshgen-smoke-status",
            "--runs-dir",
            str(tmp_path / "runs"),
            "--json",
            "--strict",
        ]
    )

    assert args.command == "media-meshgen-smoke-status"
    assert args.runs_dir == tmp_path / "runs"
    assert args.json is True
    assert args.strict is True


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


def test_media_meshgen_smoke_status_finds_successful_smoke_receipts(tmp_path: Path):
    run_root = tmp_path / "runs" / "smoke-ok"
    meshgen_dir = run_root / "20_meshgen"
    meshgen_dir.mkdir(parents=True)
    (meshgen_dir / "media_command.stl").write_text(
        "solid smoke\nendsolid smoke\n",
        encoding="ascii",
    )
    (meshgen_dir / "smoke.json").write_text(
        json.dumps(
            {
                "status": "succeeded",
                "provider_id": "media_command",
                "output_path": "20_meshgen/media_command.stl",
            }
        ),
        encoding="utf-8",
    )

    status = build_media_meshgen_smoke_status(tmp_path / "runs")

    assert status["overall_status"] == "passed"
    assert status["successful_smoke_count"] == 1
    assert status["latest_successful_smoke"]["run_id"] == "smoke-ok"


def test_media_meshgen_smoke_status_finds_nested_smoke_receipts(tmp_path: Path):
    run_root = tmp_path / "runs" / "media-meshgen-smoke" / "smoke-ok"
    meshgen_dir = run_root / "20_meshgen"
    meshgen_dir.mkdir(parents=True)
    (meshgen_dir / "media_command.stl").write_text(
        "solid smoke\nendsolid smoke\n",
        encoding="ascii",
    )
    (meshgen_dir / "smoke.json").write_text(
        json.dumps(
            {
                "status": "succeeded",
                "provider_id": "media_command",
                "output_path": "20_meshgen/media_command.stl",
            }
        ),
        encoding="utf-8",
    )

    status = build_media_meshgen_smoke_status(tmp_path / "runs")

    assert status["overall_status"] == "passed"
    assert status["successful_smoke_count"] == 1
    assert status["latest_successful_smoke"]["run_id"] == "smoke-ok"
    assert (
        status["latest_successful_smoke"]["smoke_path"]
        == "media-meshgen-smoke/smoke-ok/20_meshgen/smoke.json"
    )


def test_media_meshgen_smoke_status_reports_missing_when_no_success_exists(tmp_path: Path):
    status = build_media_meshgen_smoke_status(tmp_path / "runs")

    assert status["overall_status"] == "missing"
    assert status["successful_smoke_count"] == 0
    assert "media-meshgen-smoke" in status["action"]


def test_media_meshgen_smoke_status_cli_prints_json_and_gates_strictly(
    tmp_path: Path,
    capsys,
):
    exit_code = main(
        [
            "media-meshgen-smoke-status",
            "--runs-dir",
            str(tmp_path / "runs"),
            "--json",
            "--strict",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert payload["overall_status"] == "missing"
    assert payload["successful_smoke_count"] == 0
    assert "media-meshgen-smoke" in payload["action"]


def test_media_meshgen_smoke_status_cli_prints_human_summary(
    tmp_path: Path,
    capsys,
):
    run_root = tmp_path / "runs" / "smoke-ok"
    meshgen_dir = run_root / "20_meshgen"
    meshgen_dir.mkdir(parents=True)
    (meshgen_dir / "media_command.stl").write_text(
        "solid smoke\nendsolid smoke\n",
        encoding="ascii",
    )
    (meshgen_dir / "smoke.json").write_text(
        json.dumps(
            {
                "status": "succeeded",
                "provider_id": "media_command",
                "output_path": "20_meshgen/media_command.stl",
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "media-meshgen-smoke-status",
            "--runs-dir",
            str(tmp_path / "runs"),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Media Meshgen Smoke Status" in captured.out
    assert "overall: passed" in captured.out
    assert "latest successful smoke: smoke-ok" in captured.out
