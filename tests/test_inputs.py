from __future__ import annotations

import json
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


def test_prepare_still_image_saves_selected_reference_and_manifest(tmp_path: Path):
    source = tmp_path / "reference.png"
    source.write_bytes(b"fake png bytes")

    result = prepare_input(source, tmp_path / "input-work")

    assert result.kind == InputKind.IMAGE
    assert result.needs_mesh_generation is True
    assert result.mesh_artifact is None
    assert [artifact.kind for artifact in result.selected_references] == [ArtifactKind.CLEANED_FRAME]
    assert result.selected_references[0].path.read_bytes() == b"fake png bytes"

    assert result.contact_sheet is not None
    assert result.contact_sheet.kind == ArtifactKind.PREVIEW
    manifest = json.loads(result.contact_sheet.path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["input_kind"] == "image"
    assert manifest["reference_count"] == 1
    assert manifest["references"][0]["path"].endswith("selected/reference.png")

    statuses = {(receipt.stage, receipt.status) for receipt in result.receipts}
    assert ("classify_input", StageStatus.SUCCEEDED) in statuses
    assert ("extract_references", StageStatus.SUCCEEDED) in statuses
    assert ("select_references", StageStatus.SUCCEEDED) in statuses
    assert ("background_removal", StageStatus.SKIPPED) in statuses
    assert ("normalize_lighting", StageStatus.SKIPPED) in statuses
    assert ("contact_sheet", StageStatus.SUCCEEDED) in statuses


def test_prepare_gif_and_video_return_not_implemented_receipts(tmp_path: Path):
    for filename, expected_kind in (("turntable.gif", InputKind.GIF), ("clip.mov", InputKind.VIDEO)):
        source = tmp_path / filename
        source.write_bytes(b"fake media bytes")

        result = prepare_input(source, tmp_path / f"work-{source.stem}")

        assert result.kind == expected_kind
        assert result.needs_mesh_generation is False
        assert result.selected_references == ()
        assert result.contact_sheet is not None

        receipt_by_stage = {receipt.stage: receipt for receipt in result.receipts}
        assert receipt_by_stage["extract_references"].status == StageStatus.SKIPPED
        assert "not implemented" in receipt_by_stage["extract_references"].message
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
