"""Dependency-free local web server helpers for PrintPipe."""

from __future__ import annotations

import json
import mimetypes
from collections.abc import Iterable
from dataclasses import dataclass
from html import escape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlsplit

from printpipe.web.artifacts import discover_run_artifacts, resolve_artifact_request
from printpipe.web.options import selector_catalog
from printpipe.web.status import build_run_status


_HTML_MEDIA_TYPE = "text/html; charset=utf-8"
_JSON_MEDIA_TYPE = "application/json; charset=utf-8"
_TEXT_MEDIA_TYPE = "text/plain; charset=utf-8"
_STATIC_PREFIX = "/static/"
_RUNS_PREFIX = "/runs/"
_HTML_SUFFIXES = {".html", ".htm"}


@dataclass(frozen=True)
class WebResponse:
    """Small response container shared by tests and the HTTP adapter."""

    status: int
    body: bytes
    headers: tuple[tuple[str, str], ...] = ()

    @property
    def text(self) -> str:
        return self.body.decode("utf-8")

    def header(self, name: str) -> str | None:
        lower_name = name.lower()
        for key, value in self.headers:
            if key.lower() == lower_name:
                return value
        return None

    @classmethod
    def html(cls, html: str, *, status: int = HTTPStatus.OK) -> WebResponse:
        return cls.from_text(html, status=status, content_type=_HTML_MEDIA_TYPE)

    @classmethod
    def json(cls, payload: dict[str, Any], *, status: int = HTTPStatus.OK) -> WebResponse:
        body = json.dumps(payload, sort_keys=True).encode("utf-8") + b"\n"
        return cls(
            int(status),
            body,
            (
                ("Content-Type", _JSON_MEDIA_TYPE),
                ("Content-Length", str(len(body))),
            ),
        )

    @classmethod
    def from_text(
        cls,
        text: str,
        *,
        status: int = HTTPStatus.OK,
        content_type: str = _TEXT_MEDIA_TYPE,
    ) -> WebResponse:
        body = text.encode("utf-8")
        return cls(
            int(status),
            body,
            (
                ("Content-Type", content_type),
                ("Content-Length", str(len(body))),
            ),
        )


class PrintPipeWebApp:
    """Tiny local app that can be called directly or adapted to http.server."""

    def __init__(
        self,
        static_roots: Iterable[str | Path] = (),
        *,
        runs_dir: str | Path | None = None,
    ) -> None:
        self.static_roots = tuple(Path(root) for root in static_roots)
        self.runs_dir = Path(runs_dir) if runs_dir is not None else None

    def handle(self, target: str, *, method: str = "GET") -> WebResponse:
        """Return a response for a local request target such as ``/health``."""

        request_method = method.upper()
        if request_method not in {"GET", "HEAD"}:
            return self._method_not_allowed()

        path = urlsplit(target).path or "/"
        if path in {"/", "/index.html"}:
            return self.home_response()
        if path == "/health":
            return self.health_response()
        if path.startswith(_STATIC_PREFIX):
            return self.static_response(path.removeprefix(_STATIC_PREFIX))
        if path.startswith(_RUNS_PREFIX):
            return self.run_artifact_response(path.removeprefix(_RUNS_PREFIX))

        return self.not_found_response()

    def home_response(self) -> WebResponse:
        return WebResponse.html(self.render_home())

    def health_response(self) -> WebResponse:
        return WebResponse.json({"service": "printpipe-web", "status": "ok"})

    def static_response(self, relative_url_path: str) -> WebResponse:
        static_path = self._find_static_html(relative_url_path)
        if static_path is None:
            return self.not_found_response()

        body = static_path.read_bytes()
        return WebResponse(
            HTTPStatus.OK,
            body,
            (
                ("Content-Type", _HTML_MEDIA_TYPE),
                ("Content-Length", str(len(body))),
            ),
        )

    def run_artifact_response(self, relative_url_path: str) -> WebResponse:
        if self.runs_dir is None:
            return self.not_found_response()

        parts = relative_url_path.split("/", 2)
        if len(parts) != 3 or parts[1] != "artifacts":
            return self.not_found_response()

        run_root = self._run_root(parts[0])
        if run_root is None:
            return self.not_found_response()

        try:
            artifact_path = resolve_artifact_request(run_root, parts[2])
        except (FileNotFoundError, ValueError):
            return self.not_found_response()

        body = artifact_path.read_bytes()
        media_type = _media_type(artifact_path)
        return WebResponse(
            HTTPStatus.OK,
            body,
            (
                ("Content-Type", media_type),
                ("Content-Length", str(len(body))),
                (
                    "Content-Disposition",
                    f'attachment; filename="{_content_disposition_filename(artifact_path.name)}"',
                ),
            ),
        )

    def not_found_response(self) -> WebResponse:
        return WebResponse.from_text(
            "Not found\n",
            status=HTTPStatus.NOT_FOUND,
            content_type=_TEXT_MEDIA_TYPE,
        )

    def render_home(self) -> str:
        page_links = self._static_page_links()
        if page_links:
            pages = "\n".join(
                f'        <li><a href="{escape(href, quote=True)}">{escape(label)}</a></li>'
                for href, label in page_links
            )
        else:
            pages = '        <li class="muted">No local pages found.</li>'

        return "\n".join(
            [
                "<!doctype html>",
                '<html lang="en">',
                "<head>",
                '  <meta charset="utf-8">',
                '  <meta name="viewport" content="width=device-width, initial-scale=1">',
                "  <title>PrintPipe Local</title>",
                f"  <style>{_CSS}</style>",
                "</head>",
                "<body>",
                "  <main>",
                "    <header>",
                "      <p>Reference to print</p>",
                "      <h1>PrintPipe</h1>",
                "    </header>",
                self._render_create_run_panel(),
                self._render_recent_runs_panel(),
                '    <section class="panel">',
                "      <h2>Service</h2>",
                '      <p><a href="/health">Health check</a></p>',
                "    </section>",
                '    <section class="panel">',
                "      <h2>Local Pages</h2>",
                "      <ul>",
                pages,
                "      </ul>",
                "    </section>",
                "  </main>",
                "</body>",
                "</html>",
                "",
            ]
        )

    def _render_create_run_panel(self) -> str:
        catalog = selector_catalog()
        defaults = catalog["defaults"]
        printer_options = _render_select_options(
            catalog["printers"],
            selected_id=defaults["printer_id"],
        )
        material_options = _render_select_options(
            catalog["materials"],
            selected_id=defaults["material_id"],
        )
        return "\n".join(
            [
                '    <section class="panel create-panel">',
                "      <h2>New Run</h2>",
                '      <form class="run-form" method="post" action="/runs" enctype="multipart/form-data">',
                '        <label class="drop-zone">',
                '          <span>Input reference</span>',
                '          <input type="file" name="input" accept="image/*,video/*,.gif,.stl,.glb,.gltf,.obj,.3mf">',
                "        </label>",
                '        <div class="field-grid">',
                "          <label>",
                "            <span>Printer</span>",
                f'            <select name="printer_id">{printer_options}</select>',
                "          </label>",
                "          <label>",
                "            <span>Filament</span>",
                f'            <select name="material_id">{material_options}</select>',
                "          </label>",
                "          <label>",
                "            <span>Target length (mm)</span>",
                '            <input type="number" name="target_length_mm" min="1" step="0.1" value="100">',
                "          </label>",
                "        </div>",
                '        <button type="submit">Start run</button>',
                "      </form>",
                "    </section>",
            ]
        )

    def _render_recent_runs_panel(self) -> str:
        statuses = self._recent_run_statuses()
        if not statuses:
            body = '<p class="muted">No runs found.</p>'
        else:
            body = '<div class="run-list">\n' + "\n".join(
                self._render_run_card(status)
                for status in statuses
            ) + "\n      </div>"

        return "\n".join(
            [
                '    <section class="panel runs-panel">',
                "      <h2>Runs</h2>",
                f"      {body}",
                "    </section>",
            ]
        )

    def _render_run_card(self, status: dict[str, Any]) -> str:
        run_id = str(status.get("run_id", "unknown-run"))
        progress = status.get("progress", {})
        progress_state = str(progress.get("state", "unknown"))
        progress_percent = str(progress.get("percent", 0))
        warning_count = str(status.get("warning_count", 0))
        report_html = status.get("report", {}).get("html", {})
        report_link = ""
        if report_html.get("present"):
            report_link = (
                f'<a href="/static/{quote(run_id, safe="")}/80_reports/run_report.html">'
                "Open report"
                "</a>"
            )
        artifact_links = self._run_artifact_links(run_id)
        artifacts = ""
        if artifact_links:
            artifacts = (
                '\n        <ul class="artifact-links">\n'
                + "\n".join(
                    "          <li>"
                    f'<a href="{escape(link.href, quote=True)}">{escape(link.label)}</a>'
                    f' <span class="muted">{escape(link.category)}</span>'
                    "</li>"
                    for link in artifact_links
                )
                + "\n        </ul>"
            )

        return "\n".join(
            [
                '        <article class="run-card">',
                "          <div>",
                f"            <h3>{escape(run_id)}</h3>",
                (
                    "            "
                    f'<span class="status status-{_class_name(progress_state)}">'
                    f"{escape(progress_state)}"
                    "</span>"
                ),
                "          </div>",
                f'          <progress max="100" value="{escape(progress_percent)}"></progress>',
                f'          <p class="muted">{escape(progress_percent)}% complete, {escape(warning_count)} warnings</p>',
                f"          {report_link}",
                f"{artifacts}",
                "        </article>",
            ]
        )

    def _recent_run_statuses(self) -> list[dict[str, Any]]:
        if self.runs_dir is None:
            return []

        runs_dir = self.runs_dir.expanduser().resolve()
        if not runs_dir.exists():
            return []

        run_roots = [
            path
            for path in runs_dir.iterdir()
            if path.is_dir() and (path / "manifest.json").exists()
        ]
        run_roots.sort(key=lambda path: path.stat().st_mtime, reverse=True)

        statuses = []
        for run_root in run_roots[:8]:
            try:
                statuses.append(build_run_status(run_root))
            except (OSError, json.JSONDecodeError, ValueError):
                continue
        return statuses

    def _run_artifact_links(self, run_id: str) -> list[Any]:
        if self.runs_dir is None:
            return []
        run_root = self._run_root(run_id)
        if run_root is None:
            return []
        try:
            return list(
                discover_run_artifacts(
                    run_root,
                    link_base=f"/runs/{quote(run_id, safe='')}/artifacts/",
                )
            )
        except (OSError, ValueError):
            return []

    def _method_not_allowed(self) -> WebResponse:
        body = b"Method not allowed\n"
        return WebResponse(
            HTTPStatus.METHOD_NOT_ALLOWED,
            body,
            (
                ("Content-Type", _TEXT_MEDIA_TYPE),
                ("Content-Length", str(len(body))),
                ("Allow", "GET, HEAD"),
            ),
        )

    def _static_page_links(self) -> list[tuple[str, str]]:
        links: list[tuple[str, str]] = []
        for root in self.static_roots:
            if not root.exists():
                continue
            for path in sorted(root.rglob("*")):
                if not path.is_file() or path.suffix.lower() not in _HTML_SUFFIXES:
                    continue
                relative_path = path.relative_to(root).as_posix()
                links.append((f"{_STATIC_PREFIX}{quote(relative_path, safe='/.')}", relative_path))
        return links

    def _find_static_html(self, relative_url_path: str) -> Path | None:
        relative_path = unquote(relative_url_path).lstrip("/")
        if not relative_path:
            return None
        if Path(relative_path).suffix.lower() not in _HTML_SUFFIXES:
            return None

        for root in self.static_roots:
            if not root.exists():
                continue
            root_path = root.expanduser().resolve()
            candidate = (root_path / relative_path).resolve()
            if not _is_relative_to(candidate, root_path):
                continue
            if candidate.is_file():
                return candidate
        return None

    def _run_root(self, run_id: str) -> Path | None:
        if self.runs_dir is None:
            return None
        if "\x00" in run_id or "/" in run_id or "\\" in run_id:
            return None
        root = self.runs_dir.expanduser().resolve()
        candidate = (root / unquote(run_id)).resolve()
        if not _is_relative_to(candidate, root):
            return None
        if not candidate.is_dir():
            return None
        return candidate


def create_app(
    static_roots: Iterable[str | Path] = (),
    *,
    runs_dir: str | Path | None = None,
) -> PrintPipeWebApp:
    """Create the local web app without binding a socket."""

    roots = [Path(root) for root in static_roots]
    if runs_dir is not None:
        roots.append(Path(runs_dir))
    return PrintPipeWebApp(static_roots=roots, runs_dir=runs_dir)


def create_server(
    app: PrintPipeWebApp | None = None,
    *,
    host: str = "127.0.0.1",
    port: int = 0,
) -> ThreadingHTTPServer:
    """Create, but do not start, a stdlib HTTP server for the app."""

    web_app = app or create_app()
    handler = _handler_for(web_app)
    return ThreadingHTTPServer((host, port), handler)


def serve(
    app: PrintPipeWebApp | None = None,
    *,
    host: str = "127.0.0.1",
    port: int = 8000,
    runs_dir: str | Path | None = None,
) -> None:
    """Run the local server until interrupted."""

    web_app = app or create_app(runs_dir=runs_dir)
    server = create_server(web_app, host=host, port=port)
    try:
        server.serve_forever()
    finally:
        server.server_close()


def _handler_for(app: PrintPipeWebApp) -> type[BaseHTTPRequestHandler]:
    class PrintPipeRequestHandler(BaseHTTPRequestHandler):
        server_version = "PrintPipeWeb/0.1"

        def do_GET(self) -> None:
            self._send(app.handle(self.path, method="GET"))

        def do_HEAD(self) -> None:
            self._send(app.handle(self.path, method="HEAD"), include_body=False)

        def do_POST(self) -> None:
            self._send(app.handle(self.path, method="POST"))

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _send(self, response: WebResponse, *, include_body: bool = True) -> None:
            self.send_response(response.status)
            for key, value in response.headers:
                self.send_header(key, value)
            self.end_headers()
            if include_body:
                self.wfile.write(response.body)

    return PrintPipeRequestHandler


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _render_select_options(
    options: list[dict[str, Any]],
    *,
    selected_id: str,
) -> str:
    rendered = []
    for option in options:
        option_id = str(option.get("id", ""))
        selected = " selected" if option_id == selected_id else ""
        label = str(option.get("label", option_id))
        description = str(option.get("description", ""))
        rendered.append(
            f'<option value="{escape(option_id, quote=True)}"'
            f'{selected} title="{escape(description, quote=True)}">'
            f"{escape(label)}"
            "</option>"
        )
    return "".join(rendered)


def _media_type(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    if path.suffix.lower() == ".3mf":
        return "model/3mf"
    return guessed or "application/octet-stream"


def _content_disposition_filename(filename: str) -> str:
    return filename.replace("\\", "_").replace('"', "_").replace("\n", "_").replace("\r", "_")


def _class_name(value: str) -> str:
    cleaned = "".join(
        character if character.isalnum() or character == "-" else "-"
        for character in value.lower()
    )
    return cleaned.strip("-") or "unknown"


_CSS = """
    :root {
      color-scheme: light;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.45;
      color: #1f2933;
      background: #f7f8fa;
    }
    body {
      margin: 0;
    }
    main {
      max-width: 920px;
      margin: 0 auto;
      padding: 32px 20px 56px;
    }
    header {
      margin-bottom: 24px;
    }
    header p {
      margin: 0 0 4px;
      color: #52606d;
      font-size: 0.92rem;
      text-transform: uppercase;
    }
    h1, h2 {
      margin: 0;
      line-height: 1.2;
    }
    h1 {
      font-size: 2rem;
    }
    h2 {
      font-size: 1.12rem;
      margin-bottom: 10px;
    }
    .panel {
      background: #ffffff;
      border: 1px solid #d9e2ec;
      border-radius: 8px;
      margin: 16px 0;
      padding: 18px;
    }
    .run-form {
      display: grid;
      gap: 14px;
    }
    .drop-zone {
      border: 1px dashed #9fb3c8;
      border-radius: 8px;
      display: grid;
      gap: 8px;
      padding: 18px;
    }
    .field-grid,
    .run-list {
      display: grid;
      gap: 12px;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    }
    label span {
      display: block;
      color: #52606d;
      font-size: 0.86rem;
      font-weight: 700;
      margin-bottom: 6px;
    }
    input,
    select,
    button {
      box-sizing: border-box;
      font: inherit;
      min-height: 40px;
      width: 100%;
    }
    input,
    select {
      border: 1px solid #bcccdc;
      border-radius: 6px;
      padding: 8px 10px;
    }
    button {
      background: #0b5cad;
      border: 0;
      border-radius: 6px;
      color: #ffffff;
      cursor: pointer;
      font-weight: 700;
      max-width: 180px;
      padding: 8px 14px;
    }
    .run-card {
      border: 1px solid #e4e7eb;
      border-radius: 8px;
      padding: 14px;
    }
    .run-card h3 {
      margin: 0 0 8px;
      word-break: break-word;
    }
    progress {
      height: 10px;
      width: 100%;
    }
    .muted {
      color: #52606d;
    }
    .artifact-links {
      margin-top: 10px;
    }
    ul {
      margin: 0;
      padding-left: 20px;
    }
    li + li {
      margin-top: 8px;
    }
    a {
      color: #0b5cad;
      text-decoration: none;
    }
    a:hover {
      text-decoration: underline;
    }
""".strip()


__all__ = [
    "PrintPipeWebApp",
    "WebResponse",
    "create_app",
    "create_server",
    "serve",
]
