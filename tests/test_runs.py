from __future__ import annotations

import json
from pathlib import Path

import pytest

from printpipe.contracts import InputKind
from printpipe.runs.paths import create_run, infer_input_kind, make_run_id


def test_infer_input_kind_accepts_supported_references():
    assert infer_input_kind(Path("photo.png")) == InputKind.IMAGE
    assert infer_input_kind(Path("loop.gif")) == InputKind.GIF
    assert infer_input_kind(Path("clip.mp4")) == InputKind.VIDEO
    assert infer_input_kind(Path("part.stl")) == InputKind.MESH


def test_infer_input_kind_rejects_unknown_suffix():
    with pytest.raises(ValueError, match="unsupported input type"):
        infer_input_kind(Path("notes.txt"))


def test_make_run_id_uses_safe_slug():
    run_id = make_run_id(Path("My Slipper!.gif"))

    assert run_id.endswith("-my-slipper")
    assert "!" not in run_id


def test_create_run_copies_input_and_writes_manifest(tmp_path: Path):
    source = tmp_path / "reference.gif"
    source.write_bytes(b"gif bytes")
    layout = create_run(source, tmp_path / "runs", run_id="run-001")

    assert layout.root.name == "run-001"
    assert layout.original_input.read_bytes() == b"gif bytes"
    for directory in (
        layout.input_dir,
        layout.frames_dir,
        layout.meshgen_dir,
        layout.repair_dir,
        layout.geometry_dir,
        layout.profiles_dir,
        layout.bundle_dir,
        layout.slice_dir,
        layout.reports_dir,
    ):
        assert directory.exists()

    manifest = json.loads(layout.manifest_path.read_text())
    assert manifest["run_id"] == "run-001"
    assert manifest["input"]["kind"] == "gif"
    assert manifest["input"]["stored_path"] == "00_input/reference.gif"

