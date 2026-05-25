from __future__ import annotations

import json
from pathlib import Path

import pytest

from printpipe.web.artifacts import (
    ArtifactLink,
    discover_run_artifacts,
    link_for_artifact,
    resolve_artifact_request,
)


def test_discover_run_artifacts_returns_common_local_download_links(tmp_path: Path):
    run_root = tmp_path / "run-123"
    input_path = run_root / "00_input" / "reference image.png"
    raw_mesh = run_root / "20_meshgen" / "raw mesh.stl"
    repaired_mesh = run_root / "30_repair" / "repaired mesh.stl"
    bundle = run_root / "60_bundle" / "print ready.3mf"
    slice_log = run_root / "70_slice" / "slice.log"
    report_html = run_root / "80_reports" / "run_report.html"
    report_json = run_root / "80_reports" / "run_report.json"
    preview = run_root / "80_reports" / "bed fit.png"
    for artifact_path in (
        input_path,
        raw_mesh,
        repaired_mesh,
        bundle,
        slice_log,
        report_html,
        preview,
    ):
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text("artifact\n", encoding="utf-8")

    report_json.write_text(
        json.dumps(
            {
                "artifacts": [
                    {
                        "kind": "original_input",
                        "path": "00_input/reference image.png",
                        "label": "Original input",
                    },
                    {
                        "kind": "generated_mesh",
                        "path": "20_meshgen/raw mesh.stl",
                        "label": "Generated mesh",
                    },
                    {
                        "kind": "repaired_mesh",
                        "path": "30_repair/repaired mesh.stl",
                        "label": "Repaired mesh",
                    },
                    {
                        "kind": "3mf",
                        "path": "60_bundle/print ready.3mf",
                        "label": "Bambu bundle",
                    },
                    {
                        "kind": "slice_log",
                        "path": "70_slice/slice.log",
                        "label": "Slice log",
                    },
                    {
                        "kind": "preview",
                        "path": "80_reports/bed fit.png",
                        "label": "Bed fit preview",
                    },
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    links = discover_run_artifacts(
        run_root,
        link_base="/runs/run-123/artifacts/",
    )

    assert [link.category for link in links] == [
        "original_input",
        "reports",
        "reports",
        "generated_mesh",
        "repaired_mesh",
        "bundle",
        "slice_log",
        "preview",
    ]
    assert all(isinstance(link, ArtifactLink) for link in links)
    assert [link.path for link in links] == [
        "00_input/reference image.png",
        "80_reports/run_report.html",
        "80_reports/run_report.json",
        "20_meshgen/raw mesh.stl",
        "30_repair/repaired mesh.stl",
        "60_bundle/print ready.3mf",
        "70_slice/slice.log",
        "80_reports/bed fit.png",
    ]
    assert links[0].href == "/runs/run-123/artifacts/00_input/reference%20image.png"
    assert links[4].href == "/runs/run-123/artifacts/30_repair/repaired%20mesh.stl"
    assert links[5].download_name == "print ready.3mf"
    assert links[5].media_type == "model/3mf"


def test_link_for_artifact_normalizes_safe_absolute_paths(tmp_path: Path):
    run_root = tmp_path / "run-456"
    artifact_path = run_root / "60_bundle" / "final bundle.3mf"
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_bytes(b"3mf")

    link = link_for_artifact(
        run_root,
        artifact_path,
        category="bundle",
        label="Final bundle",
        link_base="/artifacts/",
    )

    assert link == ArtifactLink(
        category="bundle",
        label="Final bundle",
        path="60_bundle/final bundle.3mf",
        href="/artifacts/60_bundle/final%20bundle.3mf",
        download_name="final bundle.3mf",
        media_type="model/3mf",
        size_bytes=3,
    )


def test_discover_run_artifacts_includes_geometry_frame_bundle_and_slice_outputs(
    tmp_path: Path,
):
    run_root = tmp_path / "run-artifacts"
    paths = (
        run_root / "10_frames" / "contact_sheet.html",
        run_root / "40_geometry" / "shoe_oriented.stl",
        run_root / "40_geometry" / "bed_fit.svg",
        run_root / "60_bundle" / "shoe.3mf",
        run_root / "70_slice" / "slice_result.json",
        run_root / "70_slice" / "bambu_slice_stdout.log",
        run_root / "80_reports" / "run_report.html",
        run_root / "80_reports" / "run_report.json",
    )
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("artifact\n", encoding="utf-8")

    links = discover_run_artifacts(run_root)

    assert [(link.category, link.label, link.path) for link in links] == [
        ("reports", "Run report HTML", "80_reports/run_report.html"),
        ("reports", "Run report JSON", "80_reports/run_report.json"),
        (
            "oriented_mesh",
            "Oriented mesh",
            "40_geometry/shoe_oriented.stl",
        ),
        ("bundle", "Bambu bundle", "60_bundle/shoe.3mf"),
        ("slice_log", "Slice result JSON", "70_slice/slice_result.json"),
        ("slice_log", "Bambu slicer stdout log", "70_slice/bambu_slice_stdout.log"),
        ("preview", "Bed fit SVG preview", "40_geometry/bed_fit.svg"),
        ("preview", "Contact sheet HTML preview", "10_frames/contact_sheet.html"),
    ]
    assert links[3].download_name == "shoe.3mf"
    assert links[3].media_type == "model/3mf"
    assert links[4].media_type == "application/json"
    assert links[6].media_type == "image/svg+xml"
    assert links[7].media_type == "text/html"


def test_resolve_artifact_request_rejects_traversal_and_symlink_escape(tmp_path: Path):
    run_root = tmp_path / "run-789"
    safe_path = run_root / "20_meshgen" / "raw mesh.stl"
    safe_path.parent.mkdir(parents=True)
    safe_path.write_text("mesh\n", encoding="utf-8")
    outside_path = tmp_path / "outside.txt"
    outside_path.write_text("secret\n", encoding="utf-8")

    assert resolve_artifact_request(run_root, "20_meshgen/raw%20mesh.stl") == safe_path

    for request_path in ("../outside.txt", "%2e%2e/outside.txt", "/tmp/outside.txt"):
        with pytest.raises(ValueError, match="outside run root"):
            resolve_artifact_request(run_root, request_path)

    symlink_path = run_root / "escape"
    try:
        symlink_path.symlink_to(outside_path)
    except OSError:
        pytest.skip("filesystem does not allow symlinks")

    with pytest.raises(ValueError, match="outside run root"):
        resolve_artifact_request(run_root, "escape")
