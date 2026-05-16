from __future__ import annotations

import json
from pathlib import Path

from printpipe.contracts import Artifact, ArtifactKind, StageReceipt, StageStatus
from printpipe.reports import build_run_report_dict, write_run_report
from printpipe.reports.html import write_html_report
from printpipe.runs.paths import create_run
from printpipe.web import PrintPipeWebApp, create_app
from printpipe.web import server as web_server


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
