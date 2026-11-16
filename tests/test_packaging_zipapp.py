from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from printpipe.cli import main
from printpipe.packaging.zipapp import build_zipapp_package


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_build_zipapp_package_creates_executable_printpipe_artifact(tmp_path: Path) -> None:
    output_path = tmp_path / "printpipe.pyz"

    result = build_zipapp_package(
        project_root=REPO_ROOT,
        output_path=output_path,
    )

    assert result["status"] == "ok"
    assert result["artifact_path"] == str(output_path)
    assert result["entrypoint"] == "printpipe.cli:main"
    assert output_path.exists()
    assert output_path.read_bytes().startswith(b"#!/usr/bin/env python3")

    proc = subprocess.run(
        [sys.executable, str(output_path), "--version"],
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0
    assert proc.stdout.strip() == "printpipe 0.1.0"
    assert proc.stderr == ""

    smoke_proc = subprocess.run(
        [
            sys.executable,
            str(output_path),
            "package-smoke",
            "--platform",
            "macos",
            "--runs-dir",
            str(tmp_path / "runs"),
            "--json",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    smoke_payload = json.loads(smoke_proc.stdout)

    assert smoke_proc.returncode == 0
    assert smoke_payload["status"] == "ok"
    assert Path(smoke_payload["run_root"]).exists()
    json.dumps(result)


def test_cli_build_zipapp_json_reports_artifact(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "dist" / "printpipe.pyz"

    exit_code = main(["build-zipapp", "--output", str(output_path), "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["status"] == "ok"
    assert payload["artifact_path"] == str(output_path)
    assert output_path.exists()


def test_prp08_zipapp_serves_static_assets_over_http(tmp_path):
    archive = tmp_path / 'printpipe.pyz'
    build_zipapp_package(project_root=REPO_ROOT, output_path=archive)
    script = '''
import sys, threading, urllib.request, json
sys.path.insert(0, sys.argv[1])
from printpipe.web import create_app, create_server
server = create_server(create_app(runs_dir=sys.argv[2]), port=0)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
try:
    results = []
    for name in ('viewer.js', 'status.js', 'settings.css'):
        with urllib.request.urlopen(f'http://127.0.0.1:{server.server_port}/static/{name}') as response:
            results.append([response.status, len(response.read())])
    print(json.dumps(results))
finally:
    server.shutdown()
    server.server_close()
    thread.join()
'''
    proc = subprocess.run([sys.executable, '-S', '-c', script, str(archive), str(tmp_path / 'runs')],
                          text=True, capture_output=True)
    assert proc.returncode == 0, proc.stderr
    assert all(status == 200 and length > 0 for status, length in json.loads(proc.stdout))
