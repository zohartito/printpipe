from __future__ import annotations

import json
from pathlib import Path

from printpipe.cli import main


def test_run_creates_prepared_input_reports_and_prints_paths(tmp_path: Path, capsys):
    source = tmp_path / "reference.png"
    source.write_bytes(b"not really an image yet")
    runs_dir = tmp_path / "runs"

    exit_code = main(["run", str(source), "--runs-dir", str(runs_dir)])

    captured = capsys.readouterr()
    assert exit_code == 0
    run_roots = list(runs_dir.iterdir())
    assert len(run_roots) == 1
    run_root = run_roots[0]
    assert (run_root / "manifest.json").exists()
    assert (run_root / "10_frames" / "selected" / "reference.png").exists()
    assert (run_root / "10_frames" / "contact_sheet_manifest.json").exists()
    assert (run_root / "80_reports" / "run_report.json").exists()
    assert (run_root / "80_reports" / "run_report.md").exists()
    assert (run_root / "80_reports" / "run_report.html").exists()
    assert "run id:" in captured.out
    assert f"run root: {run_root}" in captured.out
    assert f"report json: {run_root / '80_reports' / 'run_report.json'}" in captured.out
    assert f"report markdown: {run_root / '80_reports' / 'run_report.md'}" in captured.out
    assert f"report html: {run_root / '80_reports' / 'run_report.html'}" in captured.out

    report = json.loads((run_root / "80_reports" / "run_report.json").read_text(encoding="utf-8"))
    stages = {(stage["stage"], stage["status"]) for stage in report["stages"]}
    assert ("classify_input", "succeeded") in stages
    assert ("extract_references", "succeeded") in stages
    assert ("select_references", "succeeded") in stages
    assert ("contact_sheet", "succeeded") in stages


def test_run_existing_stl_writes_bundle_reports_and_checklist(tmp_path: Path, capsys):
    source = (
        Path(__file__).parent
        / "fixtures"
        / "objects"
        / "existing_stl_pipeline"
        / "tiny_tetrahedron.stl"
    )
    runs_dir = tmp_path / "runs"

    exit_code = main(["run", str(source), "--runs-dir", str(runs_dir)])

    captured = capsys.readouterr()
    assert exit_code == 0
    run_root = next(runs_dir.iterdir())
    assert (run_root / "40_geometry" / "tiny_tetrahedron_oriented.stl").exists()
    assert (run_root / "60_bundle" / "existing_stl_tiny_tetrahedron.3mf").exists()
    assert (run_root / "80_reports" / "run_report.html").exists()
    assert f"run root: {run_root}" in captured.out

    report = json.loads((run_root / "80_reports" / "run_report.json").read_text(encoding="utf-8"))
    stages = {(stage["stage"], stage["status"]) for stage in report["stages"]}
    assert ("bundle", "succeeded") in stages
    assert ("slice", "skipped") in stages
    assert report["pre_print_checklist"]


def test_status_reads_manifest_and_report_summary(tmp_path: Path, capsys):
    source = tmp_path / "reference.png"
    source.write_bytes(b"fake image")
    runs_dir = tmp_path / "runs"
    assert main(["run", str(source), "--runs-dir", str(runs_dir)]) == 0
    capsys.readouterr()
    run_root = next(runs_dir.iterdir())

    exit_code = main(["status", str(run_root)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert f"run id: {run_root.name}" in captured.out
    assert f"run root: {run_root}" in captured.out
    assert "manifest: present" in captured.out
    assert "input: image" in captured.out
    assert f"report json: {run_root / '80_reports' / 'run_report.json'}" in captured.out
    assert f"report markdown: {run_root / '80_reports' / 'run_report.md'}" in captured.out
    assert f"report html: {run_root / '80_reports' / 'run_report.html'}" in captured.out
    assert "stages: classify_input=succeeded" in captured.out
    assert "warnings: 0" in captured.out


def test_status_reports_missing_run_report_for_manifest_only_run(tmp_path: Path, capsys):
    source = tmp_path / "reference.stl"
    source.write_text("solid fake\nendsolid fake\n", encoding="utf-8")
    runs_dir = tmp_path / "runs"
    assert main(["init-run", str(source), "--runs-dir", str(runs_dir)]) == 0
    capsys.readouterr()
    run_root = next(runs_dir.iterdir())

    exit_code = main(["status", str(run_root)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert f"run id: {run_root.name}" in captured.out
    assert "manifest: present" in captured.out
    assert "input: mesh" in captured.out
    assert "report json: missing" in captured.out
    assert "report markdown: missing" in captured.out
    assert "report html: missing" in captured.out


def test_open_report_prints_html_path_without_launching_browser(tmp_path: Path, capsys):
    source = tmp_path / "reference.png"
    source.write_bytes(b"fake image")
    runs_dir = tmp_path / "runs"
    assert main(["run", str(source), "--runs-dir", str(runs_dir)]) == 0
    capsys.readouterr()
    run_root = next(runs_dir.iterdir())

    exit_code = main(["open-report", str(run_root)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.strip() == str(run_root / "80_reports" / "run_report.html")
    assert captured.err == ""
