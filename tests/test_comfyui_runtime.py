from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from printpipe.cli import build_parser, main
from printpipe.meshgen.comfyui_runtime import preflight_comfyui_runtime


class _ComfyHandler(BaseHTTPRequestHandler):
    responses: dict[str, tuple[int, dict[str, object]]] = {}

    def do_GET(self) -> None:
        status, payload = self.responses.get(
            self.path,
            (404, {"error": "not found"}),
        )
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return None


def _serve_comfyui_like(responses: dict[str, tuple[int, dict[str, object]]]) -> str:
    handler = type("ComfyHandler", (_ComfyHandler,), {"responses": responses})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return f"http://127.0.0.1:{server.server_port}"


def test_preflight_comfyui_runtime_marks_ready_when_api_and_saveglb_exist() -> None:
    url = _serve_comfyui_like(
        {
            "/system_stats": (200, {"system": {"os": "posix"}}),
            "/object_info": (200, {"LoadImage": {}, "SaveGLB": {}}),
        }
    )

    report = preflight_comfyui_runtime(url)

    assert report["status"] == "ready"
    assert report["api_reachable"] is True
    assert report["object_info_reachable"] is True
    assert report["missing_nodes"] == []


def test_preflight_comfyui_runtime_marks_missing_saveglb_action_required() -> None:
    url = _serve_comfyui_like(
        {
            "/system_stats": (200, {"system": {"os": "posix"}}),
            "/object_info": (200, {"LoadImage": {}}),
        }
    )

    report = preflight_comfyui_runtime(url)

    assert report["status"] == "action_required"
    assert report["missing_nodes"] == ["SaveGLB"]
    assert "SaveGLB" in report["warnings"][0]


def test_preflight_comfyui_runtime_handles_non_object_info_json() -> None:
    url = _serve_comfyui_like(
        {
            "/system_stats": (200, {"system": {"os": "posix"}}),
            "/object_info": (200, ["SaveGLB"]),
        }
    )

    report = preflight_comfyui_runtime(url)

    assert report["status"] == "action_required"
    assert report["object_info_reachable"] is False
    assert "response was not a JSON object" in report["warnings"][0]


def test_comfyui_preflight_parser_accepts_url_timeout_and_json() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "media-meshgen-comfyui-preflight",
            "--url",
            "http://127.0.0.1:8188",
            "--timeout",
            "0.25",
            "--json",
        ]
    )

    assert args.command == "media-meshgen-comfyui-preflight"
    assert args.url == "http://127.0.0.1:8188"
    assert args.timeout == 0.25
    assert args.json is True


def test_comfyui_preflight_cli_prints_json(capsys) -> None:
    url = _serve_comfyui_like(
        {
            "/system_stats": (200, {"system": {"os": "posix"}}),
            "/object_info": (200, {"SaveGLB": {}}),
        }
    )

    exit_code = main(["media-meshgen-comfyui-preflight", "--url", url, "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["status"] == "ready"
    assert payload["comfyui_url"] == url


def test_comfyui_preflight_cli_strict_fails_when_required_node_missing() -> None:
    url = _serve_comfyui_like(
        {
            "/system_stats": (200, {"system": {"os": "posix"}}),
            "/object_info": (200, {"LoadImage": {}}),
        }
    )

    exit_code = main(
        [
            "media-meshgen-comfyui-preflight",
            "--url",
            url,
            "--strict",
        ]
    )

    assert exit_code == 2
