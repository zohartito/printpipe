from __future__ import annotations

import json
import sys
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
    assert receipt_by_stage["background_removal"].status == StageStatus.SUCCEEDED
    assert receipt_by_stage["background_removal"].metrics["semantic_background_removed"] is False
    assert receipt_by_stage["normalize_lighting"].status == StageStatus.SUCCEEDED
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
        assert receipt_by_stage["background_removal"].status == StageStatus.SUCCEEDED
        assert receipt_by_stage["normalize_lighting"].status == StageStatus.SUCCEEDED
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
