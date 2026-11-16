from __future__ import annotations

import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import sys
import threading
from pathlib import Path

import pytest

from printpipe.contracts import ArtifactKind, InputKind, StageStatus
from printpipe.inputs import classify_input_path, prepare_input


def test_classify_input_path_accepts_supported_input_types():
    assert classify_input_path(Path("reference.PNG")) == InputKind.IMAGE
    assert classify_input_path(Path("turntable.gif")) == InputKind.GIF
    assert classify_input_path(Path("clip.MP4")) == InputKind.VIDEO
    assert classify_input_path(Path("scan.stl")) == InputKind.MESH


def test_classify_input_path_rejects_unknown_suffix():
    with pytest.raises(ValueError, match="unsupported input type"):
        classify_input_path(Path("notes.txt"))


class FakeFrameExtractor:
    name = "fake_ffmpeg"

    def __init__(self, frame_count: int = 3) -> None:
        self.frame_count = frame_count
        self.calls: list[tuple[Path, Path, int]] = []

    def extract_frames(self, input_path: Path, output_dir: Path, max_frames: int) -> tuple[Path, ...]:
        self.calls.append((input_path, output_dir, max_frames))
        output_dir.mkdir(parents=True, exist_ok=True)
        frame_paths: list[Path] = []
        for index in range(min(self.frame_count, max_frames)):
            frame_path = output_dir / f"frame_{index + 1:06d}.png"
            frame_path.write_bytes(f"fake frame {index}".encode("ascii"))
            frame_paths.append(frame_path)
        return tuple(frame_paths)


def test_prepare_still_image_saves_extracted_cleaned_selected_reference_and_manifest(tmp_path: Path):
    source = tmp_path / "reference.png"
    source.write_bytes(b"fake png bytes")
    work_dir = tmp_path / "input-work"

    result = prepare_input(source, work_dir)

    assert result.kind == InputKind.IMAGE
    assert result.needs_mesh_generation is True
    assert result.mesh_artifact is None
    assert [artifact.kind for artifact in result.selected_references] == [ArtifactKind.CLEANED_FRAME]
    assert (work_dir / "extracted" / "reference.png").read_bytes() == b"fake png bytes"
    assert (work_dir / "cleaned" / "reference.png").read_bytes() == b"fake png bytes"
    assert result.selected_references[0].path == work_dir / "selected" / "reference.png"
    assert result.selected_references[0].path.read_bytes() == b"fake png bytes"
    assert result.selected_references[0].metadata["semantic_background_removed"] is False
    assert result.selected_references[0].metadata["lighting_normalized"] is False

    assert result.contact_sheet is not None
    assert result.contact_sheet.kind == ArtifactKind.PREVIEW
    assert result.contact_sheet.path.name == "contact_sheet_manifest.json"
    manifest = json.loads(result.contact_sheet.path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["input_kind"] == "image"
    assert manifest["reference_count"] == 1
    assert manifest["references"][0]["path"].endswith("selected/reference.png")
    assert manifest["preview_items"][0]["path"].endswith("selected/reference.png")
    assert manifest["html_path"].endswith("contact_sheet.html")

    html_path = work_dir / "contact_sheet.html"
    assert html_path.exists()
    html = html_path.read_text(encoding="utf-8")
    assert "PrintPipe Contact Sheet" in html
    assert "reference.png" in html
    assert 'src="selected/reference.png"' in html
    assert "selected_reference_000" in html

    receipt_by_stage = {receipt.stage: receipt for receipt in result.receipts}
    assert receipt_by_stage["classify_input"].status == StageStatus.SUCCEEDED
    assert receipt_by_stage["extract_references"].status == StageStatus.SUCCEEDED
    assert receipt_by_stage["extract_references"].metrics["candidate_count"] == 1
    assert receipt_by_stage["background_removal"].status == StageStatus.SKIPPED
    assert receipt_by_stage["background_removal"].metrics["semantic_background_removed"] is False
    assert receipt_by_stage["normalize_lighting"].status == StageStatus.SKIPPED
    assert receipt_by_stage["normalize_lighting"].metrics["lighting_normalized"] is False
    assert receipt_by_stage["select_references"].status == StageStatus.SUCCEEDED
    assert receipt_by_stage["select_references"].metrics["candidate_count"] == 1
    assert receipt_by_stage["contact_sheet"].status == StageStatus.SUCCEEDED
    assert [artifact.path.name for artifact in receipt_by_stage["contact_sheet"].artifacts] == [
        "contact_sheet_manifest.json",
        "contact_sheet.html",
    ]


def test_prepare_gif_and_video_extract_with_fake_runner_and_select_references(tmp_path: Path):
    for filename, expected_kind in (("turntable.gif", InputKind.GIF), ("clip.mov", InputKind.VIDEO)):
        source = tmp_path / filename
        source.write_bytes(b"fake media bytes")
        work_dir = tmp_path / f"work-{source.stem}"
        extractor = FakeFrameExtractor(frame_count=3)

        result = prepare_input(source, work_dir, max_references=2, frame_extractor=extractor)

        assert result.kind == expected_kind
        assert result.needs_mesh_generation is True
        assert len(result.selected_references) == 2
        assert extractor.calls == [(source.resolve(), work_dir.resolve() / "extracted", 8)]
        assert (work_dir / "extracted" / "frame_000001.png").exists()
        assert (work_dir / "cleaned" / "frame_000001.png").exists()
        assert result.selected_references[0].path == work_dir / "selected" / "frame_000001.png"
        assert result.selected_references[0].path.read_bytes() == b"fake frame 0"
        assert result.contact_sheet is not None
        manifest = json.loads(result.contact_sheet.path.read_text(encoding="utf-8"))
        assert manifest["input_kind"] == expected_kind.value
        assert manifest["reference_count"] == 2
        assert [item["label"] for item in manifest["preview_items"]] == [
            "selected_reference_000",
            "selected_reference_001",
        ]

        receipt_by_stage = {receipt.stage: receipt for receipt in result.receipts}
        assert receipt_by_stage["extract_references"].status == StageStatus.SUCCEEDED
        assert receipt_by_stage["extract_references"].metrics["candidate_count"] == 3
        assert receipt_by_stage["extract_references"].metrics["extractor"] == "fake_ffmpeg"
        assert receipt_by_stage["background_removal"].status == StageStatus.SKIPPED
        assert receipt_by_stage["normalize_lighting"].status == StageStatus.SKIPPED
        assert receipt_by_stage["select_references"].status == StageStatus.SUCCEEDED
        assert receipt_by_stage["select_references"].metrics["selected_count"] == 2
        assert receipt_by_stage["contact_sheet"].status == StageStatus.SUCCEEDED


def test_select_references_spreads_gif_video_frames_across_the_candidate_set(
    tmp_path: Path,
):
    source = tmp_path / "turntable.gif"
    source.write_bytes(b"fake media bytes")
    work_dir = tmp_path / "work"
    extractor = FakeFrameExtractor(frame_count=5)

    result = prepare_input(source, work_dir, max_references=3, frame_extractor=extractor)

    assert [artifact.metadata["selected_from"] for artifact in result.selected_references] == [
        str(work_dir / "cleaned" / "frame_000001.png"),
        str(work_dir / "cleaned" / "frame_000003.png"),
        str(work_dir / "cleaned" / "frame_000005.png"),
    ]
    assert [artifact.metadata["source_frame_index"] for artifact in result.selected_references] == [
        0,
        2,
        4,
    ]
    assert {
        artifact.metadata["selection_strategy"] for artifact in result.selected_references
    } == {"representative_frame_spread"}

    receipt_by_stage = {receipt.stage: receipt for receipt in result.receipts}
    assert receipt_by_stage["select_references"].metrics["selection_strategy"] == (
        "representative_frame_spread"
    )
    assert receipt_by_stage["select_references"].metrics["selected_source_frame_indices"] == [
        0,
        2,
        4,
    ]


def test_clean_references_runs_configured_background_and_lighting_commands(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    source = tmp_path / "reference.png"
    source.write_bytes(b"fake png bytes")
    command_script = tmp_path / "frame_command.py"
    command_script.write_text(
        "from pathlib import Path\n"
        "import sys\n"
        "source = Path(sys.argv[1])\n"
        "target = Path(sys.argv[2])\n"
        "prefix = sys.argv[3].encode('ascii')\n"
        "target.parent.mkdir(parents=True, exist_ok=True)\n"
        "target.write_bytes(prefix + b':' + source.read_bytes())\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(
        "PRINTPIPE_BACKGROUND_REMOVAL_COMMAND",
        f"{sys.executable} {command_script} {{input}} {{output}} bg",
    )
    monkeypatch.setenv(
        "PRINTPIPE_LIGHTING_NORMALIZATION_COMMAND",
        f"{sys.executable} {command_script} {{input}} {{output}} light",
    )

    result = prepare_input(source, tmp_path / "work")

    selected = result.selected_references[0]
    assert selected.path.read_bytes() == b"light:bg:fake png bytes"
    assert selected.metadata["semantic_background_removed"] is True
    assert selected.metadata["background_removal_method"] == "configured_command"
    assert selected.metadata["lighting_normalized"] is True
    assert selected.metadata["lighting_normalization_method"] == "configured_command"

    receipt_by_stage = {receipt.stage: receipt for receipt in result.receipts}
    assert receipt_by_stage["background_removal"].metrics["command_configured"] is True
    assert receipt_by_stage["background_removal"].metrics["semantic_background_removed"] is True
    assert receipt_by_stage["normalize_lighting"].metrics["command_configured"] is True
    assert receipt_by_stage["normalize_lighting"].metrics["lighting_normalized"] is True


def test_prepare_prompt_reports_missing_provider_configuration(tmp_path: Path):
    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("small ergonomic desk hook\n", encoding="utf-8")

    result = prepare_input(prompt_path, tmp_path / "work")

    assert result.kind == InputKind.PROMPT
    assert result.selected_references == ()
    receipt_by_stage = {receipt.stage: receipt for receipt in result.receipts}
    receipt = receipt_by_stage["prompt_reference_generation"]
    assert receipt.status == StageStatus.FAILED
    assert "prompt image provider is not configured" in receipt.message
    assert "PRINTPIPE_PROMPT_IMAGE_COMMAND" in receipt.message
    assert "OPENAI_API_KEY" in receipt.message
    assert receipt.metrics["provider"] == "none"


def test_prepare_prompt_openai_provider_requires_api_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("small ergonomic desk hook\n", encoding="utf-8")
    monkeypatch.setenv("PRINTPIPE_PROMPT_IMAGE_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = prepare_input(prompt_path, tmp_path / "work")

    receipt = {receipt.stage: receipt for receipt in result.receipts}["prompt_reference_generation"]
    assert receipt.status == StageStatus.FAILED
    assert receipt.message == "OpenAI prompt image provider requires OPENAI_API_KEY"
    assert receipt.metrics["provider"] == "openai"
    assert receipt.metrics["provider_configured"] is False
    assert receipt.metrics["provider_quote"]["privacy_mode"] == "remote_api"
    assert receipt.metrics["provider_quote"]["estimated_cost_usd"] is None


def test_prepare_prompt_openai_provider_writes_reference_image(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    requests: list[dict[str, object]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            content_length = int(self.headers["Content-Length"])
            body = self.rfile.read(content_length)
            requests.append(
                {
                    "path": self.path,
                    "authorization": self.headers.get("Authorization"),
                    "json": json.loads(body.decode("utf-8")),
                }
            )
            response = {
                "data": [
                    {
                        "b64_json": base64.b64encode(b"fake openai png bytes").decode("ascii"),
                    }
                ],
                "usage": {"total_tokens": 7},
            }
            encoded = json.dumps(response).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        prompt_path = tmp_path / "prompt.txt"
        prompt_path.write_text("small ergonomic desk hook\n", encoding="utf-8")
        monkeypatch.setenv("PRINTPIPE_PROMPT_IMAGE_PROVIDER", "openai")
        monkeypatch.setenv("OPENAI_API_KEY", "test-api-key")
        monkeypatch.setenv("PRINTPIPE_OPENAI_IMAGE_BASE_URL", f"http://127.0.0.1:{server.server_port}/v1")
        monkeypatch.setenv("PRINTPIPE_OPENAI_IMAGE_MODEL", "gpt-image-test")
        monkeypatch.setenv("PRINTPIPE_OPENAI_IMAGE_SIZE", "1024x1024")
        monkeypatch.setenv("PRINTPIPE_OPENAI_IMAGE_QUALITY", "low")
        monkeypatch.setenv("PRINTPIPE_OPENAI_IMAGE_ESTIMATED_COST_USD", "0.012")
        monkeypatch.setenv("PRINTPIPE_PROMPT_IMAGE_MAX_COST_USD", "0.05")

        result = prepare_input(prompt_path, tmp_path / "work")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert requests == [
        {
            "path": "/v1/images/generations",
            "authorization": "Bearer test-api-key",
            "json": {
                "model": "gpt-image-test",
                "prompt": "small ergonomic desk hook",
                "n": 1,
                "size": "1024x1024",
                "quality": "low",
                "background": "auto",
                "output_format": "png",
            },
        }
    ]
    assert result.selected_references[0].path.read_bytes() == b"fake openai png bytes"
    assert result.selected_references[0].metadata["extraction_method"] == "openai_image_generation"
    assert result.selected_references[0].metadata["prompt_image_provider"] == "openai"
    assert result.selected_references[0].metadata["model"] == "gpt-image-test"

    receipt = {receipt.stage: receipt for receipt in result.receipts}["prompt_reference_generation"]
    assert receipt.status == StageStatus.SUCCEEDED
    assert receipt.metrics["provider"] == "openai"
    assert receipt.metrics["model"] == "gpt-image-test"
    assert receipt.metrics["usage"] == {"total_tokens": 7}
    assert receipt.metrics["provider_quote"] == {
        "provider": "openai",
        "privacy_mode": "remote_api",
        "estimated_seconds": 45.0,
        "estimated_cost_usd": 0.012,
        "cost_estimate_configured": True,
        "max_cost_usd": 0.05,
        "remote_upload": True,
        "stores_prompt_with_provider": True,
    }


def test_prepare_prompt_openai_provider_fails_closed_when_cost_cap_has_no_estimate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("small ergonomic desk hook\n", encoding="utf-8")
    monkeypatch.setenv("PRINTPIPE_PROMPT_IMAGE_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-api-key")
    monkeypatch.setenv("PRINTPIPE_PROMPT_IMAGE_MAX_COST_USD", "0.01")
    monkeypatch.delenv("PRINTPIPE_OPENAI_IMAGE_ESTIMATED_COST_USD", raising=False)

    result = prepare_input(prompt_path, tmp_path / "work")

    receipt = {receipt.stage: receipt for receipt in result.receipts}["prompt_reference_generation"]
    assert receipt.status == StageStatus.FAILED
    assert receipt.message == (
        "OpenAI prompt image cost cap cannot be checked because "
        "PRINTPIPE_OPENAI_IMAGE_ESTIMATED_COST_USD is not set"
    )
    assert receipt.metrics["provider"] == "openai"
    assert receipt.metrics["provider_quote"]["max_cost_usd"] == 0.01
    assert receipt.metrics["provider_quote"]["estimated_cost_usd"] is None


def test_prepare_prompt_openai_provider_blocks_cost_above_cap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("small ergonomic desk hook\n", encoding="utf-8")
    monkeypatch.setenv("PRINTPIPE_PROMPT_IMAGE_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-api-key")
    monkeypatch.setenv("PRINTPIPE_OPENAI_IMAGE_ESTIMATED_COST_USD", "0.25")
    monkeypatch.setenv("PRINTPIPE_PROMPT_IMAGE_MAX_COST_USD", "0.05")

    result = prepare_input(prompt_path, tmp_path / "work")

    receipt = {receipt.stage: receipt for receipt in result.receipts}["prompt_reference_generation"]
    assert receipt.status == StageStatus.FAILED
    assert receipt.message == "OpenAI prompt image estimated cost 0.25 USD exceeds cap 0.05 USD"
    assert receipt.metrics["provider"] == "openai"
    assert receipt.metrics["provider_quote"]["estimated_cost_usd"] == 0.25
    assert receipt.metrics["provider_quote"]["max_cost_usd"] == 0.05


def test_prepare_prompt_command_provider_records_local_zero_cost_quote(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("small ergonomic desk hook\n", encoding="utf-8")
    fake_prompt_image = tmp_path / "fake_prompt_image.py"
    fake_prompt_image.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import argparse",
                "parser = argparse.ArgumentParser()",
                "parser.add_argument('--prompt-file', required=True)",
                "parser.add_argument('--output', required=True)",
                "args = parser.parse_args()",
                "Path(args.output).write_bytes(b'fake png')",
                "",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv(
        "PRINTPIPE_PROMPT_IMAGE_COMMAND",
        f"{sys.executable} {fake_prompt_image} --prompt-file {{prompt_file}} --output {{output}}",
    )

    result = prepare_input(prompt_path, tmp_path / "work", prompt_image_provider="command")

    receipt = {receipt.stage: receipt for receipt in result.receipts}["prompt_reference_generation"]
    assert receipt.status == StageStatus.SUCCEEDED
    assert receipt.metrics["provider_quote"] == {
        "provider": "command",
        "privacy_mode": "local_or_user_configured",
        "estimated_seconds": None,
        "estimated_cost_usd": 0.0,
        "cost_estimate_configured": True,
        "max_cost_usd": None,
        "remote_upload": "unknown",
        "stores_prompt_with_provider": "unknown",
    }


def test_prepare_gif_and_video_skip_frame_extraction_when_no_runner_is_available(tmp_path: Path):
    for filename, expected_kind in (("turntable.gif", InputKind.GIF), ("clip.mov", InputKind.VIDEO)):
        source = tmp_path / filename
        source.write_bytes(b"fake media bytes")

        result = prepare_input(source, tmp_path / f"work-{source.stem}", use_system_ffmpeg=False)

        assert result.kind == expected_kind
        assert result.needs_mesh_generation is False
        assert result.selected_references == ()
        assert result.contact_sheet is not None

        receipt_by_stage = {receipt.stage: receipt for receipt in result.receipts}
        assert receipt_by_stage["extract_references"].status == StageStatus.SKIPPED
        assert "ffmpeg" in receipt_by_stage["extract_references"].message
        assert receipt_by_stage["extract_references"].metrics["candidate_count"] == 0
        assert receipt_by_stage["background_removal"].status == StageStatus.SKIPPED
        assert receipt_by_stage["normalize_lighting"].status == StageStatus.SKIPPED
        assert receipt_by_stage["select_references"].status == StageStatus.SKIPPED
        assert receipt_by_stage["contact_sheet"].status == StageStatus.SUCCEEDED


def test_prepare_existing_mesh_routes_without_media_processing(tmp_path: Path):
    source = tmp_path / "existing.3mf"
    source.write_bytes(b"fake mesh package")

    result = prepare_input(source, tmp_path / "mesh-work")

    assert result.kind == InputKind.MESH
    assert result.needs_mesh_generation is False
    assert result.selected_references == ()
    assert result.contact_sheet is None
    assert result.mesh_artifact is not None
    assert result.mesh_artifact.kind == ArtifactKind.ORIGINAL_INPUT
    assert result.mesh_artifact.path == source
    assert result.mesh_artifact.metadata["route"] == "existing_mesh_import"

    statuses = {(receipt.stage, receipt.status) for receipt in result.receipts}
    assert ("route_existing_mesh", StageStatus.SUCCEEDED) in statuses
    assert ("extract_references", StageStatus.SKIPPED) in statuses


def test_prp19_provider_errors_do_not_leak_credentials(tmp_path, monkeypatch):
    import io
    import urllib.error
    from printpipe.inputs import processor

    marker = 'synthetic-audit-credential'
    monkeypatch.setenv('OPENAI_API_KEY', marker)
    def rejected(*args, **kwargs):
        body = ('{"Authorization":"Bearer ' + marker + '","api_key":"synthetic-other"}' + 'x' * 10000).encode()
        raise urllib.error.HTTPError('https://provider.invalid', 401, 'Unauthorized', {}, io.BytesIO(body))
    monkeypatch.setattr(processor.urllib.request, 'urlopen', rejected)
    try:
        processor._run_openai_prompt_image_provider(prompt='cube', output_path=tmp_path / 'image.png')
    except processor.FrameExtractionError as exc:
        leaked = marker in str(exc) or 'synthetic-other' in str(exc)
        assert leaked is False
        assert '401' in str(exc)
        assert len(str(exc)) < 256
    else:
        pytest.fail('expected failed provider request')


def test_prp19_safe_diagnostic_reaches_failure_receipt(tmp_path, monkeypatch):
    import io
    import urllib.error
    from printpipe.inputs import processor

    monkeypatch.setenv('OPENAI_API_KEY', 'synthetic-receipt-key')
    monkeypatch.setenv('PRINTPIPE_PROMPT_IMAGE_PROVIDER', 'openai')
    def rejected(*args, **kwargs):
        raise urllib.error.HTTPError('https://provider.invalid', 401, 'Unauthorized', {},
                                    io.BytesIO(b'Authorization: Bearer synthetic-receipt-key'))
    monkeypatch.setattr(processor.urllib.request, 'urlopen', rejected)
    prompt = tmp_path / 'prompt.txt'
    prompt.write_text('cube')
    result = prepare_input(prompt, tmp_path / 'work')
    receipt = next(r for r in result.receipts if r.stage == 'prompt_reference_generation')
    assert receipt.status == StageStatus.FAILED
    assert receipt.message == 'OpenAI prompt image request failed with HTTP 401'
