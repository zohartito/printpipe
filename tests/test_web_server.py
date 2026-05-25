from __future__ import annotations

import json
from pathlib import Path

from printpipe.contracts import Artifact, ArtifactKind, StageReceipt, StageStatus
from printpipe.reports import build_run_report_dict, write_run_report
from printpipe.reports.html import write_html_report
from printpipe.runs.paths import create_run
from printpipe.web import PrintPipeWebApp, create_app
from printpipe.web import server as web_server


def _multipart_form_body(
    *,
    fields: dict[str, str],
    file_field: str,
    filename: str,
    content_type: str,
    file_content: bytes,
) -> tuple[bytes, str]:
    boundary = "printpipe-test-boundary"
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode("ascii"),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("ascii"),
                value.encode("utf-8"),
                b"\r\n",
            ]
        )
    chunks.extend(
        [
            f"--{boundary}\r\n".encode("ascii"),
            (
                f'Content-Disposition: form-data; name="{file_field}"; '
                f'filename="{filename}"\r\n'
            ).encode("ascii"),
            f"Content-Type: {content_type}\r\n\r\n".encode("ascii"),
            file_content,
            b"\r\n",
            f"--{boundary}--\r\n".encode("ascii"),
        ]
    )
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def test_home_response_renders_status_and_static_page_links(tmp_path: Path):
    report = tmp_path / "run_report.html"
    report.write_text("<!doctype html><h1>Run Report</h1>\n", encoding="utf-8")

    app = create_app(static_roots=(tmp_path,))

    response = app.handle("/")

    assert response.status == 200
    assert response.header("Content-Type") == "text/html; charset=utf-8"
    assert "<!doctype html>" in response.text
    assert "PrintPipe" in response.text
    assert 'href="/static/run_report.html"' in response.text


def test_home_response_renders_launch_controls_recent_runs_and_artifacts(tmp_path: Path):
    source = tmp_path / "reference.png"
    source.write_bytes(b"fake image")
    runs_dir = tmp_path / "runs"
    layout = create_run(source, runs_dir, run_id="run-ui-001")
    bundle = layout.bundle_dir / "ready.3mf"
    bundle.write_bytes(b"bundle")
    stages = (
        StageReceipt(
            stage="slice",
            status=StageStatus.SUCCEEDED,
            message="Slice passed.",
            artifacts=(
                Artifact(
                    kind=ArtifactKind.THREEMF,
                    path=bundle,
                    label="Bambu bundle",
                ),
            ),
            metrics={"mass_g": 12.3},
        ),
    )
    report_dict = build_run_report_dict(
        layout,
        stages=stages,
        warnings=("review first layer",),
    )
    write_run_report(layout, stages=stages, warnings=("review first layer",))
    write_html_report(layout, report_dict)
    app = create_app(runs_dir=runs_dir)

    response = app.handle("/")

    assert response.status == 200
    assert "New Run" in response.text
    assert 'type="file"' in response.text
    assert "Bambu Lab P2S" in response.text
    assert "SUNLU TPU 90A Slipper" in response.text
    assert "Target length (mm)" in response.text
    assert "run-ui-001" in response.text
    assert "succeeded" in response.text
    assert "Open report" in response.text
    assert 'href="/static/run-ui-001/80_reports/run_report.html"' in response.text
    assert 'href="/runs/run-ui-001/artifacts/60_bundle/ready.3mf"' in response.text


def test_home_response_groups_run_artifacts_for_preview_report_and_download(tmp_path: Path):
    source = tmp_path / "reference.png"
    source.write_bytes(b"fake image")
    runs_dir = tmp_path / "runs"
    layout = create_run(source, runs_dir, run_id="run-artifacts-001")
    bundle = layout.bundle_dir / "ready to print.3mf"
    preview_svg = layout.reports_dir / "bed fit.svg"
    preview_html = layout.reports_dir / "preview.html"
    for artifact_path in (bundle, preview_svg, preview_html):
        artifact_path.write_text("artifact\n", encoding="utf-8")
    stages = (
        StageReceipt(
            stage="geometry",
            status=StageStatus.SUCCEEDED,
            message="Preview ready.",
            artifacts=(
                Artifact(
                    kind=ArtifactKind.PREVIEW,
                    path=preview_svg,
                    label="Bed fit preview",
                ),
                Artifact(
                    kind=ArtifactKind.PREVIEW,
                    path=preview_html,
                    label="Interactive preview",
                ),
            ),
        ),
        StageReceipt(
            stage="bundle",
            status=StageStatus.SUCCEEDED,
            message="Bundle ready.",
            artifacts=(
                Artifact(
                    kind=ArtifactKind.THREEMF,
                    path=bundle,
                    label="Bambu bundle",
                ),
            ),
        ),
    )
    report_dict = build_run_report_dict(layout, stages=stages)
    write_run_report(layout, stages=stages)
    write_html_report(layout, report_dict)
    app = create_app(runs_dir=runs_dir)

    response = app.handle("/")

    assert response.status == 200
    assert '<section class="artifact-group artifact-group-bundle">' in response.text
    assert "Downloads" in response.text
    assert (
        'href="/runs/run-artifacts-001/artifacts/60_bundle/ready%20to%20print.3mf" '
        'download="ready to print.3mf"'
    ) in response.text
    assert '<section class="artifact-group artifact-group-preview">' in response.text
    assert "Previews" in response.text
    assert 'href="/runs/run-artifacts-001/artifacts/80_reports/bed%20fit.svg"' in response.text
    assert 'href="/runs/run-artifacts-001/artifacts/80_reports/preview.html"' in response.text
    assert '<section class="artifact-group artifact-group-reports">' in response.text
    assert "Reports" in response.text
    assert 'href="/runs/run-artifacts-001/artifacts/80_reports/run_report.html"' in response.text


def test_post_runs_accepts_multipart_upload_creates_skeleton_run_and_redirects(tmp_path: Path):
    runs_dir = tmp_path / "runs"
    app = create_app(runs_dir=runs_dir)
    body, content_type = _multipart_form_body(
        fields={
            "printer_id": "bambu-p2s-0-4-nozzle",
            "material_id": "sunlu-tpu-90a-slipper",
            "target_length_mm": "123.5",
        },
        file_field="input",
        filename="reference.png",
        content_type="image/png",
        file_content=b"fake image",
    )

    response = app.handle(
        "/runs",
        method="POST",
        headers={"Content-Type": content_type},
        body=body,
    )

    run_roots = [path for path in runs_dir.iterdir() if (path / "manifest.json").exists()]
    assert response.status == 303
    assert len(run_roots) == 1
    run_root = run_roots[0]
    assert response.header("Location") == f"/static/{run_root.name}/80_reports/run_report.html"
    assert (run_root / "00_input" / "reference.png").read_bytes() == b"fake image"
    assert (run_root / "10_frames" / "selected" / "reference.png").exists()
    assert (run_root / "80_reports" / "run_report.json").exists()
    assert (run_root / "80_reports" / "run_report.md").exists()
    assert (run_root / "80_reports" / "run_report.html").exists()

    manifest = json.loads((run_root / "manifest.json").read_text(encoding="utf-8"))
    launch_options = manifest["launch_options"]
    assert launch_options["source"] == "web_form"
    assert launch_options["uploaded_filename"] == "reference.png"
    assert launch_options["printer_id"] == "bambu-p2s-0-4-nozzle"
    assert launch_options["material_id"] == "sunlu-tpu-90a-slipper"
    assert launch_options["target_length_mm"] == 123.5

    report = json.loads((run_root / "80_reports" / "run_report.json").read_text(encoding="utf-8"))
    assert report["settings_changes"] == [launch_options]
    stages = {(stage["stage"], stage["status"]) for stage in report["stages"]}
    assert ("classify_input", "succeeded") in stages
    assert ("extract_references", "succeeded") in stages
    assert ("select_references", "succeeded") in stages
    assert ("contact_sheet", "succeeded") in stages


def test_post_runs_existing_stl_creates_bundle_and_report(tmp_path: Path):
    runs_dir = tmp_path / "runs"
    app = create_app(runs_dir=runs_dir)
    source = (
        Path(__file__).parent
        / "fixtures"
        / "objects"
        / "existing_stl_pipeline"
        / "tiny_tetrahedron.stl"
    )
    body, content_type = _multipart_form_body(
        fields={
            "printer_id": "bambu-p2s-0-4-nozzle",
            "material_id": "pla",
            "target_length_mm": "50",
        },
        file_field="input",
        filename="tiny_tetrahedron.stl",
        content_type="model/stl",
        file_content=source.read_bytes(),
    )

    response = app.handle(
        "/runs",
        method="POST",
        headers={"Content-Type": content_type},
        body=body,
    )

    run_root = next(path for path in runs_dir.iterdir() if (path / "manifest.json").exists())
    assert response.status == 303
    assert response.header("Location") == f"/static/{run_root.name}/80_reports/run_report.html"
    assert (run_root / "60_bundle" / "existing_stl_tiny_tetrahedron.3mf").exists()
    assert (run_root / "40_geometry" / "tiny_tetrahedron_oriented.stl").exists()

    report = json.loads((run_root / "80_reports" / "run_report.json").read_text(encoding="utf-8"))
    assert report["settings_changes"][0]["material_id"] == "pla"
    stages = {(stage["stage"], stage["status"]) for stage in report["stages"]}
    assert ("bundle", "succeeded") in stages
    assert ("slice", "skipped") in stages
    assert report["pre_print_checklist"]


def test_run_artifact_response_serves_safe_downloads_from_runs_dir(tmp_path: Path):
    source = tmp_path / "reference.png"
    source.write_bytes(b"fake image")
    runs_dir = tmp_path / "runs"
    layout = create_run(source, runs_dir, run_id="run-download-001")
    bundle = layout.bundle_dir / "ready.3mf"
    bundle.write_bytes(b"bundle")
    app = create_app(runs_dir=runs_dir)

    response = app.handle("/runs/run-download-001/artifacts/60_bundle/ready.3mf")

    assert response.status == 200
    assert response.body == b"bundle"
    assert response.header("Content-Type") == "model/3mf"
    assert response.header("Content-Disposition") == 'attachment; filename="ready.3mf"'

    traversal = app.handle("/runs/run-download-001/artifacts/../outside.txt")
    assert traversal.status == 404


def test_health_response_returns_json_status():
    app = PrintPipeWebApp()

    response = app.handle("/health")

    assert response.status == 200
    assert response.header("Content-Type") == "application/json; charset=utf-8"
    assert json.loads(response.text) == {"service": "printpipe-web", "status": "ok"}


def test_static_response_serves_local_generated_html(tmp_path: Path):
    nested = tmp_path / "runs" / "example"
    nested.mkdir(parents=True)
    page = nested / "report & summary.html"
    html = "<!doctype html><title>Example report</title>\n"
    page.write_text(html, encoding="utf-8")
    app = PrintPipeWebApp(static_roots=(tmp_path,))

    response = app.handle("/static/runs/example/report%20%26%20summary.html")

    assert response.status == 200
    assert response.header("Content-Type") == "text/html; charset=utf-8"
    assert response.text == html


def test_static_response_rejects_path_traversal(tmp_path: Path):
    public = tmp_path / "public"
    public.mkdir()
    secret = tmp_path / "secret.html"
    secret.write_text("<!doctype html>secret\n", encoding="utf-8")
    app = PrintPipeWebApp(static_roots=(public,))

    response = app.handle("/static/../secret.html")

    assert response.status == 404
    assert "secret" not in response.text


def test_static_response_only_serves_html_files(tmp_path: Path):
    data = tmp_path / "run_report.json"
    data.write_text('{"status": "ok"}\n', encoding="utf-8")
    app = PrintPipeWebApp(static_roots=(tmp_path,))

    response = app.handle("/static/run_report.json")

    assert response.status == 404


def test_serve_builds_app_from_runs_dir_without_import_side_effects(monkeypatch, tmp_path: Path):
    calls: list[object] = []
    created_apps: list[PrintPipeWebApp] = []

    class FakeServer:
        def serve_forever(self) -> None:
            calls.append("serve_forever")

        def server_close(self) -> None:
            calls.append("server_close")

    def fake_create_server(
        app: PrintPipeWebApp | None = None,
        *,
        host: str = "127.0.0.1",
        port: int = 0,
    ) -> FakeServer:
        assert host == "0.0.0.0"
        assert port == 9876
        assert app is not None
        created_apps.append(app)
        return FakeServer()

    monkeypatch.setattr(web_server, "create_server", fake_create_server)

    web_server.serve(host="0.0.0.0", port=9876, runs_dir=tmp_path)

    assert calls == ["serve_forever", "server_close"]
    assert created_apps[0].static_roots == (tmp_path,)
    assert created_apps[0].runs_dir == tmp_path
