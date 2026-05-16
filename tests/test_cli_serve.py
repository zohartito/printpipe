from __future__ import annotations

import builtins
import sys
import types
from pathlib import Path

from printpipe.cli import build_parser, main


def test_serve_parser_defaults_do_not_import_web_server(monkeypatch):
    original_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "printpipe.web" or name.startswith("printpipe.web."):
            raise AssertionError("serve parser imported the web server")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    parser = build_parser()
    args = parser.parse_args(["serve"])

    assert args.command == "serve"
    assert args.host == "127.0.0.1"
    assert args.port == 8765
    assert args.runs_dir == Path("runs")


def test_serve_delegates_to_web_server_with_custom_options(monkeypatch, tmp_path: Path):
    calls: list[dict[str, object]] = []
    web_module = types.ModuleType("printpipe.web")
    server_module = types.ModuleType("printpipe.web.server")

    def serve(*, host: str, port: int, runs_dir: Path) -> None:
        calls.append({"host": host, "port": port, "runs_dir": runs_dir})

    server_module.serve = serve
    web_module.server = server_module
    monkeypatch.setitem(sys.modules, "printpipe.web", web_module)
    monkeypatch.setitem(sys.modules, "printpipe.web.server", server_module)

    exit_code = main(
        [
            "serve",
            "--host",
            "0.0.0.0",
            "--port",
            "9876",
            "--runs-dir",
            str(tmp_path),
        ]
    )

    assert exit_code == 0
    assert calls == [{"host": "0.0.0.0", "port": 9876, "runs_dir": tmp_path}]
