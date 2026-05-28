from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import pytest

from printpipe.cli import main
from printpipe.runs.editing import EditRecipe, EditScale, create_edit_run


def test_run_media_input_writes_failed_meshgen_report_and_returns_nonzero(
    tmp_path: Path,
    capsys,
):
    source = tmp_path / "reference.png"
    source.write_bytes(b"not really an image yet")
    runs_dir = tmp_path / "runs"

    exit_code = main(["run", str(source), "--runs-dir", str(runs_dir)])

    captured = capsys.readouterr()
    assert exit_code == 2
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
    assert "failed stage: meshgen" in captured.out
    assert "error: Hunyuan3D local command is not configured" in captured.err

    report = json.loads((run_root / "80_reports" / "run_report.json").read_text(encoding="utf-8"))
    stages = {(stage["stage"], stage["status"]) for stage in report["stages"]}
    assert ("classify_input", "succeeded") in stages
    assert ("extract_references", "succeeded") in stages
    assert ("select_references", "succeeded") in stages
    assert ("contact_sheet", "succeeded") in stages
    assert ("meshgen", "failed") in stages
    assert report["warnings"] == [
        "Hunyuan3D local command is not configured; set "
        "PRINTPIPE_HUNYUAN3D_COMMAND or pass a command path."
    ]


def test_run_media_input_with_configured_hunyuan_command_writes_bundle(
    tmp_path: Path,
    capsys,
    monkeypatch: pytest.MonkeyPatch,
):
    source_mesh = (
        Path(__file__).parent
        / "fixtures"
        / "objects"
        / "existing_stl_pipeline"
        / "tiny_tetrahedron.stl"
    )
    fake_hunyuan = tmp_path / "fake_hunyuan.py"
    fake_hunyuan.write_text(
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
    monkeypatch.setenv("PRINTPIPE_HUNYUAN3D_COMMAND", f"{sys.executable} {fake_hunyuan}")

    source = tmp_path / "reference.png"
    source.write_bytes(b"fake image")
    runs_dir = tmp_path / "runs"

    exit_code = main(["run", str(source), "--runs-dir", str(runs_dir)])

    captured = capsys.readouterr()
    assert exit_code == 0
    run_root = next(runs_dir.iterdir())
    assert f"run root: {run_root}" in captured.out
    assert (run_root / "20_meshgen" / "hunyuan3d.stl").exists()
    assert (run_root / "60_bundle" / "generated_mesh_hunyuan3d.3mf").exists()

    report = json.loads((run_root / "80_reports" / "run_report.json").read_text(encoding="utf-8"))
    stages = {(stage["stage"], stage["status"]) for stage in report["stages"]}
    assert ("meshgen", "succeeded") in stages
    assert ("mesh_repair", "succeeded") in stages
    assert ("bundle", "succeeded") in stages
    assert ("3mf", "60_bundle/generated_mesh_hunyuan3d.3mf") in {
        (artifact["kind"], artifact["path"]) for artifact in report["artifacts"]
    }


def test_run_prompt_only_without_generator_writes_failed_receipts(
    tmp_path: Path,
    capsys,
):
    runs_dir = tmp_path / "runs"

    exit_code = main(
        [
            "run",
            "--prompt",
            "small ergonomic desk hook",
            "--runs-dir",
            str(runs_dir),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    run_root = next(runs_dir.iterdir())
    assert (run_root / "00_input" / "prompt.txt").read_text(encoding="utf-8") == (
        "small ergonomic desk hook\n"
    )
    assert f"run root: {run_root}" in captured.out
    assert "failed stage: prompt_reference_generation" in captured.out
    assert "prompt image provider is not configured" in captured.err

    report = json.loads((run_root / "80_reports" / "run_report.json").read_text(encoding="utf-8"))
    stages = {(stage["stage"], stage["status"]) for stage in report["stages"]}
    assert ("classify_input", "succeeded") in stages
    assert ("prompt_reference_generation", "failed") in stages
    assert ("meshgen", "failed") in stages
    manifest = json.loads((run_root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["input"]["kind"] == "prompt"
    assert report["warnings"] == [
        "prompt image provider is not configured; set PRINTPIPE_PROMPT_IMAGE_COMMAND or set "
        "PRINTPIPE_PROMPT_IMAGE_PROVIDER=openai with OPENAI_API_KEY"
    ]


def test_run_prompt_only_with_openai_provider_without_key_writes_failed_receipts(
    tmp_path: Path,
    capsys,
    monkeypatch: pytest.MonkeyPatch,
):
    runs_dir = tmp_path / "runs"
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    exit_code = main(
        [
            "run",
            "--prompt",
            "small ergonomic desk hook",
            "--prompt-image-provider",
            "openai",
            "--runs-dir",
            str(runs_dir),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "OpenAI prompt image provider requires OPENAI_API_KEY" in captured.err
    run_root = next(runs_dir.iterdir())
    report = json.loads((run_root / "80_reports" / "run_report.json").read_text(encoding="utf-8"))
    assert report["warnings"] == ["OpenAI prompt image provider requires OPENAI_API_KEY"]


def test_run_prompt_only_with_configured_reference_and_hunyuan_writes_bundle(
    tmp_path: Path,
    capsys,
    monkeypatch: pytest.MonkeyPatch,
):
    source_mesh = (
        Path(__file__).parent
        / "fixtures"
        / "objects"
        / "existing_stl_pipeline"
        / "tiny_tetrahedron.stl"
    )
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
                "prompt = Path(args.prompt_file).read_text(encoding='utf-8')",
                "Path(args.output).write_bytes(b'fake image for ' + prompt.encode('utf-8'))",
                "",
            ]
        ),
        encoding="utf-8",
    )
    fake_hunyuan = tmp_path / "fake_hunyuan.py"
    fake_hunyuan.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import argparse",
                "parser = argparse.ArgumentParser()",
                "parser.add_argument('--output', required=True)",
                "parser.add_argument('--prompt')",
                "args, _ = parser.parse_known_args()",
                "assert args.prompt == 'small ergonomic desk hook'",
                f"Path(args.output).write_text(Path({str(source_mesh)!r}).read_text(encoding='ascii'), encoding='ascii')",
                "",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv(
        "PRINTPIPE_PROMPT_IMAGE_COMMAND",
        f"{sys.executable} {fake_prompt_image} --prompt-file {{prompt_file}} --output {{output}}",
    )
    monkeypatch.setenv("PRINTPIPE_HUNYUAN3D_COMMAND", f"{sys.executable} {fake_hunyuan}")

    runs_dir = tmp_path / "runs"

    exit_code = main(
        [
            "run",
            "--prompt",
            "small ergonomic desk hook",
            "--runs-dir",
            str(runs_dir),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    run_root = next(runs_dir.iterdir())
    assert f"run root: {run_root}" in captured.out
    assert (run_root / "10_frames" / "prompt_reference" / "prompt_reference.png").exists()
    assert (run_root / "20_meshgen" / "hunyuan3d.stl").exists()
    assert (run_root / "60_bundle" / "generated_mesh_hunyuan3d.3mf").exists()

    report = json.loads((run_root / "80_reports" / "run_report.json").read_text(encoding="utf-8"))
    stages = {(stage["stage"], stage["status"]) for stage in report["stages"]}
    assert ("prompt_reference_generation", "succeeded") in stages
    assert ("meshgen", "succeeded") in stages
    assert ("bundle", "succeeded") in stages


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


def test_run_existing_stl_accepts_material_printer_and_use_case_flags(
    tmp_path: Path,
    capsys,
):
    source = (
        Path(__file__).parent
        / "fixtures"
        / "objects"
        / "existing_stl_pipeline"
        / "tiny_tetrahedron.stl"
    )
    runs_dir = tmp_path / "runs"

    exit_code = main(
        [
            "run",
            str(source),
            "--runs-dir",
            str(runs_dir),
            "--material",
            "SUNLU TPU 90A",
            "--printer",
            "Bambu Lab P2S",
            "--use-case",
            "wearable slipper",
        ]
    )

    capsys.readouterr()
    assert exit_code == 0
    run_root = next(runs_dir.iterdir())
    report = json.loads((run_root / "80_reports" / "run_report.json").read_text(encoding="utf-8"))

    stages = {(stage["stage"], stage["status"]) for stage in report["stages"]}
    checklist = {item["id"]: item for item in report["pre_print_checklist"]}
    assert ("validation.flex_coupon", "succeeded") in stages
    assert (run_root / "40_geometry" / "flex_coupon_40x15x3.stl").exists()
    with zipfile.ZipFile(run_root / "60_bundle" / "existing_stl_tiny_tetrahedron.3mf") as archive:
        project_settings = json.loads(archive.read("Metadata/project_settings.config"))

    assert project_settings["filament_settings_id"] == ["SUNLU TPU 90A Slipper @BBL P2S"]
    assert project_settings["print_settings_id"] == "0.20mm Slipper TPU 90A @BBL P2S"
    assert project_settings["support_style"] == ["snug"]
    assert project_settings["brim_object_gap"] == ["0.12"]
    assert checklist["dry_filament"]["metadata"]["material"] == "SUNLU TPU 90A"
    assert checklist["feed_path"]["status"] == "required"
    assert checklist["flex_coupon_first"]["status"] == "required"
    assert checklist["flex_coupon_first"]["metadata"]["coupon_artifact"] == (
        "40_geometry/flex_coupon_40x15x3.stl"
    )


def test_run_slice_failure_prints_report_paths_before_returning_nonzero(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
):
    source = (
        Path(__file__).parent
        / "fixtures"
        / "objects"
        / "existing_stl_pipeline"
        / "tiny_tetrahedron.stl"
    )
    runs_dir = tmp_path / "runs"
    missing_bambu = tmp_path / "missing-bambu"

    exit_code = main(
        [
            "run",
            str(source),
            "--runs-dir",
            str(runs_dir),
            "--slice",
            "--bambu-cli",
            str(missing_bambu),
        ]
    )

    captured = capsys.readouterr()
    run_root = next(runs_dir.iterdir())
    assert exit_code == 2
    assert f"run root: {run_root}" in captured.out
    assert f"report json: {run_root / '80_reports' / 'run_report.json'}" in captured.out
    assert f"report markdown: {run_root / '80_reports' / 'run_report.md'}" in captured.out
    assert f"report html: {run_root / '80_reports' / 'run_report.html'}" in captured.out
    assert "failed stage: slice" in captured.out
    assert "error: Bambu CLI slice failed" in captured.err


def test_run_bambu_cli_requires_slice_flag(tmp_path: Path):
    source = tmp_path / "reference.stl"
    source.write_text("solid fake\nendsolid fake\n", encoding="utf-8")

    with pytest.raises(SystemExit) as raised:
        main(["run", str(source), "--bambu-cli", str(tmp_path / "fake-bambu")])

    assert raised.value.code == 2


def test_run_slice_requires_existing_mesh_or_prebuilt_bundle_for_now(tmp_path: Path):
    source = tmp_path / "reference.png"
    source.write_bytes(b"fake image")

    with pytest.raises(SystemExit) as raised:
        main(["run", str(source), "--slice"])

    assert raised.value.code == 2


def test_status_reads_manifest_and_report_summary(tmp_path: Path, capsys):
    source = tmp_path / "reference.png"
    source.write_bytes(b"fake image")
    runs_dir = tmp_path / "runs"
    assert main(["run", str(source), "--runs-dir", str(runs_dir)]) == 2
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
    assert "meshgen=failed" in captured.out
    assert "warnings: 1" in captured.out


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
    assert main(["run", str(source), "--runs-dir", str(runs_dir)]) == 2
    capsys.readouterr()
    run_root = next(runs_dir.iterdir())

    exit_code = main(["open-report", str(run_root)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.strip() == str(run_root / "80_reports" / "run_report.html")
    assert captured.err == ""


def test_open_folder_dry_run_prints_bundle_folder_without_launching(tmp_path: Path, capsys):
    source = (
        Path(__file__).parent
        / "fixtures"
        / "objects"
        / "existing_stl_pipeline"
        / "tiny_tetrahedron.stl"
    )
    runs_dir = tmp_path / "runs"
    assert main(["run", str(source), "--runs-dir", str(runs_dir)]) == 0
    capsys.readouterr()
    run_root = next(runs_dir.iterdir())

    exit_code = main(["open-folder", str(run_root), "--target", "bundle", "--dry-run"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert str(run_root / "60_bundle") in captured.out
    assert "dry run: not opened" in captured.out


def test_rebuild_edit_rebuilds_saved_edit_recipe(tmp_path: Path, capsys):
    source = (
        Path(__file__).parent
        / "fixtures"
        / "objects"
        / "existing_stl_pipeline"
        / "tiny_tetrahedron.stl"
    )
    runs_dir = tmp_path / "runs"
    assert main(["run", str(source), "--runs-dir", str(runs_dir)]) == 0
    capsys.readouterr()
    parent_root = next(runs_dir.iterdir())
    edit_layout = create_edit_run(
        parent_root,
        EditRecipe(parent_run_id=parent_root.name, scale=EditScale(y=1.2)),
    )

    exit_code = main(["rebuild-edit", str(edit_layout.root)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert f"run root: {edit_layout.root}" in captured.out
    assert f"report html: {edit_layout.reports_dir / 'run_report.html'}" in captured.out
    assert any(path.suffix == ".3mf" for path in edit_layout.bundle_dir.iterdir())
