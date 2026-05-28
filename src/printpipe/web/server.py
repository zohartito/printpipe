"""Dependency-free local web server helpers for PrintPipe."""

from __future__ import annotations

import json
import math
import mimetypes
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from email.parser import BytesParser
from email.policy import default as email_policy
from html import escape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlsplit

from printpipe.pipeline import PipelineError, run_edit_recipe_pipeline, run_existing_mesh_pipeline
from printpipe.runs import (
    EditRecipe,
    EditScale,
    EditTargets,
    GeometryIntent,
    RunLayout,
    build_run_detail,
    create_edit_run,
)
from printpipe.web.artifacts import discover_run_artifacts, resolve_artifact_request
from printpipe.web.options import selector_catalog
from printpipe.web.status import build_run_status


_HTML_MEDIA_TYPE = "text/html; charset=utf-8"
_JSON_MEDIA_TYPE = "application/json; charset=utf-8"
_TEXT_MEDIA_TYPE = "text/plain; charset=utf-8"
_STATIC_PREFIX = "/static/"
_RUNS_PREFIX = "/runs/"
_HTML_SUFFIXES = {".html", ".htm"}
_MAX_FORM_BODY_BYTES = 8 * 1024 * 1024
_MAX_UPLOAD_BYTES = 8 * 1024 * 1024
_MAX_FIELD_CHARS = 2_048
_TARGET_SIZE_FIELDS = (
    "target_length_mm",
    "target_width_mm",
    "target_height_mm",
    "target_size_mm",
)


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

    @classmethod
    def redirect(cls, location: str, *, status: int = HTTPStatus.SEE_OTHER) -> WebResponse:
        body = f"See {location}\n".encode("utf-8")
        return cls(
            int(status),
            body,
            (
                ("Content-Type", _TEXT_MEDIA_TYPE),
                ("Content-Length", str(len(body))),
                ("Location", location),
            ),
        )


@dataclass(frozen=True)
class _UploadedFile:
    field_name: str
    filename: str
    content_type: str
    content: bytes


@dataclass(frozen=True)
class _ParsedRunForm:
    upload: _UploadedFile
    launch_options: dict[str, Any]


class _FormError(ValueError):
    def __init__(self, status: HTTPStatus, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


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

    def handle(
        self,
        target: str,
        *,
        method: str = "GET",
        headers: Any | None = None,
        body: bytes = b"",
    ) -> WebResponse:
        """Return a response for a local request target such as ``/health``."""

        request_method = method.upper()
        path = urlsplit(target).path or "/"
        if request_method == "POST":
            if path == "/runs":
                return self.create_run_response(headers=headers, body=body)
            if path.startswith(_RUNS_PREFIX):
                edit_run_id = _edit_route_id(path.removeprefix(_RUNS_PREFIX))
                if edit_run_id is not None:
                    return self.create_edit_response(edit_run_id, headers=headers, body=body)
            return self._method_not_allowed()
        if request_method not in {"GET", "HEAD"}:
            return self._method_not_allowed()

        if path in {"/", "/index.html"}:
            return self.home_response()
        if path == "/favicon.ico":
            return WebResponse(int(HTTPStatus.NO_CONTENT), b"", (("Content-Length", "0"),))
        if path == "/health":
            return self.health_response()
        if path.startswith(_STATIC_PREFIX):
            return self.static_response(path.removeprefix(_STATIC_PREFIX))
        if path.startswith(_RUNS_PREFIX):
            relative_run_path = path.removeprefix(_RUNS_PREFIX)
            run_id = _run_detail_id(relative_run_path)
            if run_id is not None:
                return self.run_detail_response(run_id)
            return self.run_artifact_response(relative_run_path)

        return self.not_found_response()

    def create_run_response(self, *, headers: Any | None, body: bytes) -> WebResponse:
        if self.runs_dir is None:
            return WebResponse.from_text(
                "Runs directory is not configured.\n",
                status=HTTPStatus.SERVICE_UNAVAILABLE,
                content_type=_TEXT_MEDIA_TYPE,
            )

        try:
            form = _parse_run_form(headers=headers, body=body)
            layout = self._create_skeleton_run(form)
        except _FormError as exc:
            return WebResponse.from_text(
                f"{exc.message}\n",
                status=exc.status,
                content_type=_TEXT_MEDIA_TYPE,
            )
        except FileExistsError:
            return WebResponse.from_text(
                "A run with that id already exists. Please retry.\n",
                status=HTTPStatus.CONFLICT,
                content_type=_TEXT_MEDIA_TYPE,
            )
        except PipelineError as exc:
            return WebResponse.from_text(
                f"{exc}\n",
                status=HTTPStatus.BAD_REQUEST,
                content_type=_TEXT_MEDIA_TYPE,
            )
        except (FileNotFoundError, ValueError) as exc:
            return WebResponse.from_text(
                f"{exc}\n",
                status=HTTPStatus.BAD_REQUEST,
                content_type=_TEXT_MEDIA_TYPE,
            )

        location = f"/static/{quote(layout.run_id, safe='')}/80_reports/run_report.html"
        return WebResponse.redirect(location)

    def create_edit_response(
        self,
        run_id: str,
        *,
        headers: Any | None,
        body: bytes,
    ) -> WebResponse:
        run_root = self._run_root(run_id)
        if run_root is None:
            return self.not_found_response()

        try:
            fields = _parse_edit_form(headers=headers, body=body)
            recipe = _edit_recipe_from_fields(run_id, fields)
            edit_layout = create_edit_run(run_root, recipe)
            run_edit_recipe_pipeline(edit_layout.root)
        except _FormError as exc:
            return WebResponse.from_text(
                f"{exc.message}\n",
                status=exc.status,
                content_type=_TEXT_MEDIA_TYPE,
            )
        except PipelineError as exc:
            return WebResponse.redirect(
                f"/runs/{quote(exc.result.layout.run_id, safe='')}"
            )
        except (FileExistsError, OSError, json.JSONDecodeError, ValueError) as exc:
            return WebResponse.from_text(
                f"{exc}\n",
                status=HTTPStatus.BAD_REQUEST,
                content_type=_TEXT_MEDIA_TYPE,
            )

        return WebResponse.redirect(f"/runs/{quote(edit_layout.run_id, safe='')}")

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

    def run_detail_response(self, run_id: str) -> WebResponse:
        run_root = self._run_root(run_id)
        if run_root is None:
            return self.not_found_response()

        try:
            detail = build_run_detail(run_root)
            artifact_links = self._run_artifact_links(run_id)
        except (OSError, json.JSONDecodeError, ValueError):
            return self.not_found_response()

        return WebResponse.html(
            _render_run_detail_page(
                detail=detail,
                artifact_links=artifact_links,
            )
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
        workbench_link = f'<a href="/runs/{quote(run_id, safe="")}">Open workbench</a>'
        artifacts = _render_artifact_groups(self._run_artifact_links(run_id))

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
                f"          {workbench_link}",
                f"          {report_link}",
                f"{artifacts}",
                "        </article>",
            ]
        )

    def _recent_run_statuses(self) -> list[dict[str, Any]]:
        if self.runs_dir is None:
            return []

        try:
            runs_dir = self.runs_dir.expanduser().resolve()
            if not runs_dir.exists():
                return []
            run_roots = [
                path
                for path in runs_dir.iterdir()
                if path.is_dir() and (path / "manifest.json").exists()
            ]
            run_roots.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        except OSError:
            return []

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

    def _create_skeleton_run(self, form: _ParsedRunForm) -> RunLayout:
        runs_dir = Path(self.runs_dir).expanduser().resolve()
        incoming_dir = runs_dir / ".incoming"
        incoming_dir.mkdir(parents=True, exist_ok=True)

        safe_filename = _safe_upload_filename(form.upload.filename)
        try:
            with tempfile.TemporaryDirectory(prefix="upload-", dir=incoming_dir) as upload_dir_name:
                upload_path = Path(upload_dir_name) / safe_filename
                upload_path.write_bytes(form.upload.content)

                try:
                    result = run_existing_mesh_pipeline(
                        upload_path,
                        runs_dir,
                        material=str(form.launch_options.get("material_id", "Unknown material")),
                        printer=str(form.launch_options.get("printer_id", "Unknown printer")),
                        use_case="web run",
                        settings_changes=(form.launch_options,),
                    )
                except PipelineError as exc:
                    result = exc.result
                self._record_launch_options(result.layout, form.launch_options)
                return result.layout
        finally:
            try:
                incoming_dir.rmdir()
            except OSError:
                pass

    def _record_launch_options(self, layout: RunLayout, launch_options: dict[str, Any]) -> None:
        manifest = json.loads(layout.manifest_path.read_text(encoding="utf-8"))
        manifest["launch_options"] = launch_options
        layout.manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


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
            try:
                body = self._read_request_body()
            except _FormError as exc:
                self._send(
                    WebResponse.from_text(
                        f"{exc.message}\n",
                        status=exc.status,
                        content_type=_TEXT_MEDIA_TYPE,
                    )
                )
                return
            self._send(app.handle(self.path, method="POST", headers=self.headers, body=body))

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _read_request_body(self) -> bytes:
            raw_length = self.headers.get("Content-Length", "0")
            try:
                content_length = int(raw_length)
            except ValueError as exc:
                raise _FormError(HTTPStatus.BAD_REQUEST, "Invalid Content-Length.") from exc
            if content_length < 0:
                raise _FormError(HTTPStatus.BAD_REQUEST, "Invalid Content-Length.")
            if content_length > _MAX_FORM_BODY_BYTES:
                raise _FormError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "Form upload is too large.")
            return self.rfile.read(content_length)

        def _send(self, response: WebResponse, *, include_body: bool = True) -> None:
            self.send_response(response.status)
            for key, value in response.headers:
                self.send_header(key, value)
            self.end_headers()
            if include_body:
                self.wfile.write(response.body)

    return PrintPipeRequestHandler


def _parse_run_form(*, headers: Any | None, body: bytes) -> _ParsedRunForm:
    if len(body) > _MAX_FORM_BODY_BYTES:
        raise _FormError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "Form upload is too large.")

    content_type = _header_value(headers, "Content-Type")
    if content_type is None or "multipart/form-data" not in content_type.lower():
        raise _FormError(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "Expected multipart/form-data.")

    try:
        message = BytesParser(policy=email_policy).parsebytes(
            f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8")
            + body
        )
    except (LookupError, ValueError) as exc:
        raise _FormError(HTTPStatus.BAD_REQUEST, "Malformed multipart form data.") from exc

    if not message.is_multipart():
        raise _FormError(HTTPStatus.BAD_REQUEST, "Malformed multipart form data.")

    fields: dict[str, str] = {}
    upload: _UploadedFile | None = None
    for part in message.iter_parts():
        if part.get_content_disposition() != "form-data":
            continue
        field_name = part.get_param("name", header="content-disposition")
        if not field_name:
            continue

        payload = part.get_payload(decode=True)
        if payload is None:
            payload_text = part.get_payload()
            payload = str(payload_text).encode(part.get_content_charset() or "utf-8", "replace")

        filename = part.get_filename()
        if filename is not None:
            if field_name != "input":
                continue
            if len(payload) > _MAX_UPLOAD_BYTES:
                raise _FormError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "Uploaded input is too large.")
            upload = _UploadedFile(
                field_name=field_name,
                filename=filename,
                content_type=part.get_content_type(),
                content=payload,
            )
            continue

        if len(payload) > _MAX_FIELD_CHARS * 4:
            raise _FormError(HTTPStatus.BAD_REQUEST, f"Form field is too long: {field_name}.")
        fields[field_name] = payload.decode(part.get_content_charset() or "utf-8", "replace").strip()

    if upload is None:
        raise _FormError(HTTPStatus.BAD_REQUEST, "Missing uploaded input file.")
    if not upload.content:
        raise _FormError(HTTPStatus.BAD_REQUEST, "Uploaded input file is empty.")

    return _ParsedRunForm(upload=upload, launch_options=_launch_options(fields, upload.filename))


def _parse_edit_form(*, headers: Any | None, body: bytes) -> dict[str, str]:
    if len(body) > _MAX_FORM_BODY_BYTES:
        raise _FormError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "Edit form is too large.")

    content_type = (_header_value(headers, "Content-Type") or "").lower()
    if content_type and "application/x-www-form-urlencoded" not in content_type:
        raise _FormError(
            HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
            "Expected application/x-www-form-urlencoded.",
        )

    parsed = parse_qs(body.decode("utf-8", "replace"), keep_blank_values=True)
    fields: dict[str, str] = {}
    for key, values in parsed.items():
        if len(key) > _MAX_FIELD_CHARS:
            raise _FormError(HTTPStatus.BAD_REQUEST, "Edit form field name is too long.")
        value = values[-1] if values else ""
        if len(value) > _MAX_FIELD_CHARS:
            raise _FormError(
                HTTPStatus.BAD_REQUEST,
                f"Edit form field is too long: {key}.",
            )
        fields[key] = value.strip()
    return fields


def _edit_recipe_from_fields(run_id: str, fields: dict[str, str]) -> EditRecipe:
    opening_delta = _float_field(fields, "opening_delta_mm", default=0.0)
    return EditRecipe(
        parent_run_id=run_id,
        scale=EditScale(
            overall=_scale_field(fields, "overall_scale"),
            x=_scale_field(fields, "x_scale"),
            y=_scale_field(fields, "y_scale"),
            z=_scale_field(fields, "z_scale"),
        ),
        targets_mm=EditTargets(
            length=_optional_float_field(fields, "target_length_mm"),
            width=_optional_float_field(fields, "target_width_mm"),
            height=_optional_float_field(fields, "target_height_mm"),
        ),
        geometry_intent=GeometryIntent(
            upper_width_delta_mm=opening_delta,
            opening_width_delta_mm=opening_delta,
            arch_height_delta_mm=_float_field(fields, "arch_delta_mm", default=0.0),
            wall_thickness_mm=_optional_float_field(fields, "wall_thickness_mm"),
            flat_base=fields.get("flat_base") in {"on", "true", "1", "yes"},
        ),
        support_strategy=fields.get("support_strategy") or "auto",
        instruction=fields.get("edit_instruction", ""),
    )


def _launch_options(fields: dict[str, str], uploaded_filename: str) -> dict[str, Any]:
    catalog = selector_catalog()
    defaults = catalog["defaults"]
    printer_id = fields.get("printer_id") or defaults["printer_id"]
    material_id = fields.get("material_id") or defaults["material_id"]

    printer_labels = {str(option.get("id", "")): str(option.get("label", "")) for option in catalog["printers"]}
    material_labels = {str(option.get("id", "")): str(option.get("label", "")) for option in catalog["materials"]}
    if printer_id not in printer_labels:
        raise _FormError(HTTPStatus.BAD_REQUEST, f"Unknown printer selection: {printer_id}.")
    if material_id not in material_labels:
        raise _FormError(HTTPStatus.BAD_REQUEST, f"Unknown material selection: {material_id}.")

    options: dict[str, Any] = {
        "source": "web_form",
        "uploaded_filename": _safe_upload_filename(uploaded_filename),
        "printer_id": printer_id,
        "printer_label": printer_labels[printer_id],
        "material_id": material_id,
        "material_label": material_labels[material_id],
    }
    target_fields = {
        field_name: _positive_float(fields[field_name], field_name=field_name)
        for field_name in _TARGET_SIZE_FIELDS
        if fields.get(field_name)
    }
    if not target_fields:
        target_fields["target_length_mm"] = 100.0
    options.update(target_fields)
    return options


def _positive_float(value: str, *, field_name: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise _FormError(HTTPStatus.BAD_REQUEST, f"Invalid numeric value for {field_name}.") from exc
    if not math.isfinite(parsed) or parsed <= 0 or parsed > 10_000:
        raise _FormError(HTTPStatus.BAD_REQUEST, f"Invalid numeric value for {field_name}.")
    return parsed


def _optional_float_field(fields: dict[str, str], field_name: str) -> float | None:
    value = fields.get(field_name)
    if value in {None, ""}:
        return None
    return _float_field(fields, field_name, default=0.0)


def _float_field(fields: dict[str, str], field_name: str, *, default: float) -> float:
    value = fields.get(field_name)
    if value in {None, ""}:
        return default
    try:
        parsed = float(value)
    except ValueError as exc:
        raise _FormError(HTTPStatus.BAD_REQUEST, f"Invalid numeric value for {field_name}.") from exc
    if not math.isfinite(parsed) or abs(parsed) > 10_000:
        raise _FormError(HTTPStatus.BAD_REQUEST, f"Invalid numeric value for {field_name}.")
    return parsed


def _scale_field(fields: dict[str, str], field_name: str) -> float:
    value = _float_field(fields, field_name, default=1.0)
    if value > 10:
        value = value / 100
    if value <= 0:
        raise _FormError(HTTPStatus.BAD_REQUEST, f"Invalid numeric value for {field_name}.")
    return value


def _header_value(headers: Any | None, name: str) -> str | None:
    if headers is None:
        return None
    direct = headers.get(name) if hasattr(headers, "get") else None
    if direct is not None:
        return str(direct)
    lower_name = name.lower()
    if hasattr(headers, "items"):
        for key, value in headers.items():
            if str(key).lower() == lower_name:
                return str(value)
    return None


def _safe_upload_filename(filename: str) -> str:
    raw_name = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()
    cleaned = "".join(
        character if character.isalnum() or character in {".", "-", "_"} else "_"
        for character in raw_name
        if character not in {"\x00", "\r", "\n"}
    ).strip("._")
    if not cleaned:
        cleaned = "upload"
    if len(cleaned) <= 120:
        return cleaned

    suffix = Path(cleaned).suffix[:24]
    stem_limit = max(1, 120 - len(suffix))
    return f"{Path(cleaned).stem[:stem_limit]}{suffix}"


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


def _run_detail_id(relative_url_path: str) -> str | None:
    relative_path = unquote(relative_url_path).strip("/")
    if not relative_path or "/" in relative_path or "\\" in relative_path:
        return None
    return relative_path


def _edit_route_id(relative_url_path: str) -> str | None:
    parts = unquote(relative_url_path).strip("/").split("/")
    if len(parts) != 2 or parts[1] != "edits":
        return None
    run_id = parts[0]
    if not run_id or "/" in run_id or "\\" in run_id:
        return None
    return run_id


def _read_run_report(run_root: Path) -> dict[str, Any]:
    report_path = run_root / "80_reports" / "run_report.json"
    if not report_path.exists():
        return {}
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _render_run_detail_page(
    *,
    detail: dict[str, Any],
    artifact_links: list[Any],
) -> str:
    run_id = str(detail.get("run_id", "unknown-run"))
    verdict = _mapping(detail.get("print_verdict"))
    status_label = str(verdict.get("label") or "Review before print")
    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '  <meta charset="utf-8">',
            '  <meta name="viewport" content="width=device-width, initial-scale=1">',
            f"  <title>PrintPipe Workbench: {escape(run_id)}</title>",
            f"  <style>{_CSS}</style>",
            "</head>",
            "<body>",
            '  <main class="app run-detail-app">',
            '    <header class="topbar">',
            "      <div>",
            '        <p class="eyebrow"><a href="/">PrintPipe</a> / Model workbench</p>',
            f"        <h1>{escape(run_id)}</h1>",
            f'        <div class="run-meta">{_render_run_meta(detail)}</div>',
            "      </div>",
            (
                f'      <div class="status-chip status-chip-{escape(_state_tone(str(verdict.get("state", "review"))), quote=True)}">'
                f"{escape(status_label)}</div>"
            ),
            "    </header>",
            '    <section class="shell">',
            _render_verdict_strip(detail=detail),
            _render_model_workbench(detail=detail, artifact_links=artifact_links),
            "    </section>",
            "  </main>",
            "</body>",
            "</html>",
            "",
        ]
    )


def _render_run_meta(detail: dict[str, Any]) -> str:
    input_info = _mapping(detail.get("input"))
    printer = _mapping(detail.get("printer"))
    material = _mapping(detail.get("material"))
    profile = _mapping(detail.get("profile"))
    parts = [
        f"input: {input_info.get('kind', 'unknown')}",
        str(printer.get("label") or "printer pending"),
        str(material.get("label") or "material pending"),
        str(profile.get("label") or "profile pending"),
    ]
    return "".join(f"<span>{escape(part)}</span>" for part in parts if part)


def _render_verdict_strip(*, detail: dict[str, Any]) -> str:
    verdict = _mapping(detail.get("print_verdict"))
    reason = str(verdict.get("reason") or "Print readiness pending.")
    checks = _validation_by_key(detail)
    cards = "\n".join(
        [
            _render_score_card("Manifold", checks.get("manifold")),
            _render_score_card("Bed fit", checks.get("bed_fit")),
            _render_score_card("TPU profile", checks.get("material_profile")),
            _render_score_card("Support", checks.get("support_risk")),
            _render_score_card("Slice", checks.get("slice_success")),
        ]
    )
    return "\n".join(
        [
            '      <section class="verdict-strip" aria-label="Can this run print?">',
            '        <article class="verdict">',
            '          <p class="eyebrow">Can this run print?</p>',
            f'          <h2>{escape(str(verdict.get("label", "Review before print")))}</h2>',
            f"          <strong>{escape(_fit_issue_label(detail))}</strong>",
            f"          <p>{escape(reason)}</p>",
            f'          <p class="next-action"><span>Next action</span>{escape(_next_action_label(detail))}</p>',
            "        </article>",
            cards,
            "      </section>",
        ]
    )


def _render_score_card(label: str, check: dict[str, Any] | None) -> str:
    check = check or {"state": "review", "detail": "No check result yet."}
    state = str(check.get("state", "review"))
    tone = _state_tone(state)
    detail = str(check.get("detail", "No check result yet."))
    return "\n".join(
        [
            f'        <article class="score score-{escape(tone, quote=True)}">',
            f"          <span>{escape(label)}</span>",
            f"          <strong>{escape(_state_label(state))}</strong>",
            f"          <p>{escape(detail)}</p>",
            "        </article>",
        ]
    )


def _render_model_workbench(
    *,
    detail: dict[str, Any],
    artifact_links: list[Any],
) -> str:
    return "\n".join(
        [
            '      <section class="workbench">',
            '        <div class="canvas-zone">',
            _render_model_card(detail=detail, artifact_links=artifact_links),
            '          <div class="lower-grid">',
            _render_stage_panel(
                title="Pipeline Stages",
                stages=[
                    stage
                    for stage in _as_list(detail.get("pipeline"))
                    if isinstance(stage, dict)
                ],
                mode="pipeline",
            ),
            _render_stage_panel(
                title="Validation Results",
                stages=[
                    check
                    for check in _as_list(detail.get("validation"))
                    if isinstance(check, dict)
                ],
                mode="validation",
            ),
            "          </div>",
            "        </div>",
            _render_edit_geometry_panel(str(detail.get("run_id", "unknown-run")), detail, artifact_links),
            "      </section>",
        ]
    )


def _render_model_card(*, detail: dict[str, Any], artifact_links: list[Any]) -> str:
    preview_links = [
        link
        for link in artifact_links
        if str(getattr(link, "category", "")) == "preview"
    ]
    geometry = _mapping(detail.get("geometry"))
    validation = _validation_by_key(detail)
    bounds = _format_bounds(geometry.get("bounds_mm"))
    artifact_label = _artifact_primary_label(artifact_links)
    return "\n".join(
        [
            '          <article class="model-card" aria-label="Model workbench">',
            '            <div class="toolbar">',
            '              <div class="view-tabs" aria-label="Preview modes">',
            '                <span class="tab active" aria-current="true">Model</span>',
            '                <span class="tab">Bed Fit</span>',
            '                <span class="tab">Upper Fit</span>',
            '                <span class="tab">Support Risk</span>',
            '                <span class="tab">Slice</span>',
            "              </div>",
            f'              <p class="eyebrow">{escape(artifact_label)}</p>',
            "            </div>",
            _render_preview_placeholder(preview_links, detail=detail),
            '            <div class="model-footer">',
            _render_metric("Mesh", _state_label(str(validation.get("manifold", {}).get("state", "review")))),
            _render_metric("Bounds", bounds),
            _render_metric("Fit issue", _fit_issue_label(detail)),
            _render_metric("Slice gate", _state_label(str(validation.get("slice_success", {}).get("state", "review")))),
            "            </div>",
            "          </article>",
        ]
    )


def _render_preview_placeholder(preview_links: list[Any], *, detail: dict[str, Any]) -> str:
    geometry = _mapping(detail.get("geometry"))
    support_risk = str(geometry.get("support_risk") or "review")
    bounds = _format_bounds(geometry.get("bounds_mm"))
    primary_preview = _primary_model_preview(preview_links)
    preview_title = (
        str(getattr(primary_preview, "label", "Model preview"))
        if primary_preview is not None
        else "Model preview pending"
    )
    preview_visual = (
        f'              <img class="model-preview-image" src="{escape(str(getattr(primary_preview, "href", "")), quote=True)}" '
        f'alt="{escape(preview_title, quote=True)}">'
        if primary_preview is not None
        else '              <div class="mesh-placeholder"></div>'
    )
    links = "\n".join(
        f'              <a href="{escape(str(getattr(link, "href", "#")), quote=True)}">{escape(str(getattr(link, "label", "Preview")))}</a>'
        for link in preview_links[:3]
    )
    link_html = f'            <div class="preview-links">{links}</div>' if links else ""
    return "\n".join(
        [
            '            <figure class="model-view" aria-label="Model preview">',
            '              <div class="bed"></div>',
            preview_visual,
            f'              <figcaption class="preview-title">{escape(preview_title)}</figcaption>',
            f'              <figcaption class="risk-marker">opening risk: {escape(support_risk.title())}</figcaption>',
            f'              <figcaption class="measure measure-x">{escape(bounds)}</figcaption>',
            f'              <figcaption class="measure measure-z">{escape(_format_metric(geometry.get("print_time_minutes"), "min"))}</figcaption>',
            "            </figure>",
            link_html,
        ]
    )


def _render_metric(label: str, value: str) -> str:
    return "\n".join(
        [
            '              <div class="metric">',
            f"                <span>{escape(label)}</span>",
            f"                <strong>{escape(value)}</strong>",
            "              </div>",
        ]
    )


def _render_stage_panel(title: str, stages: list[dict[str, Any]], *, mode: str) -> str:
    rows = "\n".join(_render_stage_row(stage, mode=mode) for stage in stages)
    if not rows:
        rows = '                <p class="muted">No stage data yet.</p>'
    return "\n".join(
        [
            '            <article class="card stage-card">',
            f"              <h2>{escape(title)}</h2>",
            '              <div class="card-body stage-rail">',
            rows,
            "              </div>",
            "            </article>",
        ]
    )


def _render_stage_row(stage: dict[str, Any], *, mode: str) -> str:
    label = str(stage.get("label", "Pipeline step"))
    state = str(stage.get("state") or stage.get("status") or "unknown")
    detail = str(stage.get("detail") or stage.get("message") or "Not run yet.")
    tone = _state_tone(state)
    return "\n".join(
        [
            '                <div class="stage">',
            f'                  <span class="node node-{escape(tone, quote=True)}"></span>',
            "                  <div>",
            f"                    <h3>{escape(label)}</h3>",
            f"                    <p>{escape(detail)}</p>",
            "                  </div>",
            f'                  <span class="badge badge-{escape(tone, quote=True)}">{escape(_state_label(state))}</span>',
            "                </div>",
        ]
    )


def _render_edit_geometry_panel(
    run_id: str,
    detail: dict[str, Any],
    artifact_links: list[Any],
) -> str:
    recipe = _mapping(detail.get("edit_recipe"))
    scale = _mapping(recipe.get("scale"))
    targets = _mapping(recipe.get("targets_mm"))
    intent = _mapping(recipe.get("geometry_intent"))
    geometry = _mapping(detail.get("geometry"))
    return "\n".join(
        [
            (
                '        <form class="controls" '
                f'action="/runs/{quote(run_id, safe="")}/edits" method="post">'
            ),
            "          <h2>Edit Geometry</h2>",
            '          <div class="controls-body">',
            f'            <p class="issue-line">{escape(_fit_issue_label(detail))}</p>',
            '            <p class="muted">Tune opening width, arch clearance, sole texture, TPU-safe supports, and external spool assumptions before slicing again.</p>',
            '            <section class="input-card">',
            "              <h3>Input prompt / mesh summary</h3>",
            f"              <p>{escape(_detail_input_summary(detail))}</p>",
            f"              <p>Current geometry: {escape(_format_bounds(geometry.get('bounds_mm')))}</p>",
            f"              <p>Current issue: {escape(_fit_issue_label(detail))}</p>",
            "            </section>",
            '            <div class="control-grid">',
            _number_field("Overall scale", "overall_scale", _field_value(scale, "overall", "1.0"), suffix="x"),
            _number_field("X scale", "x_scale", _field_value(scale, "x", "1.0"), suffix="x"),
            _number_field("Y scale", "y_scale", _field_value(scale, "y", "1.0"), suffix="x"),
            _number_field("Z scale", "z_scale", _field_value(scale, "z", "1.0"), suffix="x"),
            _number_field("Target length", "target_length_mm", _field_value(targets, "length", ""), suffix="mm"),
            _number_field("Target width", "target_width_mm", _field_value(targets, "width", ""), suffix="mm"),
            _number_field("Target height", "target_height_mm", _field_value(targets, "height", ""), suffix="mm"),
            _number_field("Widen / narrow opening", "opening_delta_mm", _field_value(intent, "opening_width_delta_mm", "0"), suffix="mm"),
            _number_field("Raise / lower arch/opening", "arch_delta_mm", _field_value(intent, "arch_height_delta_mm", "0"), suffix="mm"),
            _number_field("Wall thickness", "wall_thickness_mm", _field_value(intent, "wall_thickness_mm", "2.4"), suffix="mm"),
            "            </div>",
            (
                '            <label class="check-row"><input type="checkbox" '
                f'name="flat_base"{_checked(intent.get("flat_base", True))}> Flat base</label>'
            ),
            "            <label>",
            "              <span>Support strategy</span>",
            '              <select name="support_strategy">',
            _support_option(recipe, "auto", "Auto from support risk"),
            _support_option(recipe, "snug_tree_auto", "TPU-safe snug/tree supports"),
            _support_option(recipe, "tree", "Tree supports"),
            _support_option(recipe, "minimal", "Minimal supports"),
            _support_option(recipe, "none", "No supports"),
            "              </select>",
            "            </label>",
            "            <label>",
            "              <span>Freeform edit instruction</span>",
            (
                '              <textarea name="edit_instruction" rows="4" '
                'placeholder="Example: widen the front opening by 8 mm and keep the arch lower.">'
                f'{escape(str(recipe.get("instruction", "")))}'
                "</textarea>"
            ),
            "            </label>",
            '            <div class="edit-actions">',
            '              <button class="primary" type="submit">Rebuild from edits</button>',
            "            </div>",
            (
                '            <p class="recipe-preview">Recipe preview: '
                f"opening {_signed_mm(intent.get('opening_width_delta_mm', 0))}, "
                f"arch {_signed_mm(intent.get('arch_height_delta_mm', 0))}, "
                f"Y scale {escape(_field_value(scale, 'y', '1.0'))}.</p>"
            ),
            '            <p class="muted">Creates a non-destructive edit run; original artifacts stay untouched.</p>',
            "            <section>",
            "              <h3>Artifact Links</h3>",
            _render_artifact_tiles(artifact_links),
            "            </section>",
            "          </div>",
            "        </form>",
        ]
    )


def _render_pipeline_panel(*, detail: dict[str, Any]) -> str:
    stages = [
        stage
        for stage in _as_list(detail.get("pipeline"))
        if isinstance(stage, dict)
    ]
    items = "\n".join(
        _render_pipeline_step(stage)
        for stage in stages
    )
    return "\n".join(
        [
            '    <section class="panel">',
            "      <h2>Pipeline</h2>",
            f'      <div class="pipeline-steps">{items}</div>',
            "    </section>",
        ]
    )


def _render_pipeline_step(stage: dict[str, Any]) -> str:
    label = str(stage.get("label", "Pipeline step"))
    stage_status = str(stage.get("status", "unknown"))
    message = str(stage.get("message", "Not run yet."))
    return "\n".join(
        [
            f'        <article class="pipeline-step status-border-{escape(_class_name(stage_status), quote=True)}">',
            f"          <h3>{escape(label)}</h3>",
            (
                f'          <span class="status status-{escape(_class_name(stage_status), quote=True)}">'
                f"{escape(stage_status)}</span>"
            ),
            f'          <p class="muted">{escape(message)}</p>',
            "        </article>",
        ]
    )


def _number_field(label: str, name: str, value: str, *, suffix: str) -> str:
    return "\n".join(
        [
            "            <label>",
            f"              <span>{escape(label)} ({escape(suffix)})</span>",
            (
                f'              <input type="number" name="{escape(name, quote=True)}" '
                f'value="{escape(value, quote=True)}" step="0.1">'
            ),
            "            </label>",
        ]
    )


def _validation_by_key(detail: dict[str, Any]) -> dict[str, dict[str, Any]]:
    checks: dict[str, dict[str, Any]] = {}
    for check in _as_list(detail.get("validation")):
        if not isinstance(check, dict):
            continue
        key = str(check.get("key") or _class_name(str(check.get("label", ""))))
        checks[key] = check
    return checks


def _state_tone(state: str) -> str:
    normalized = _class_name(state)
    if normalized in {"pass", "passed", "ready", "succeeded", "success"}:
        return "pass"
    if normalized in {"fail", "failed", "blocked", "error"}:
        return "fail"
    return "warn"


def _state_label(state: str) -> str:
    tone = _state_tone(state)
    if tone == "pass":
        return "Pass"
    if tone == "fail":
        return "Fail"
    return "Review"


def _format_bounds(value: Any) -> str:
    if not isinstance(value, list | tuple) or not value:
        return "Bounds pending"
    parts: list[str] = []
    for item in value[:3]:
        try:
            number = float(item)
        except (TypeError, ValueError):
            continue
        parts.append(f"{number:g}")
    if not parts:
        return "Bounds pending"
    return " x ".join(parts) + " mm"


def _format_metric(value: Any, suffix: str) -> str:
    if value in {None, ""}:
        return "pending"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{number:g} {suffix}"


def _artifact_primary_label(artifact_links: list[Any]) -> str:
    preferred_categories = ("oriented_mesh", "repaired_mesh", "generated_mesh", "preview", "bundle", "reports")
    for category in preferred_categories:
        for link in artifact_links:
            if str(getattr(link, "category", "")) == category:
                return str(getattr(link, "label", "Artifact"))
    return "preview artifact pending"


def _primary_model_preview(preview_links: list[Any]) -> Any | None:
    for link in preview_links:
        text = f"{getattr(link, 'label', '')} {getattr(link, 'path', '')}".lower()
        if "run detail" in text or "model_preview" in text or "model preview" in text:
            return link
    return None


def _fit_issue_label(detail: dict[str, Any]) -> str:
    warnings = [str(warning).lower() for warning in _as_list(detail.get("warnings"))]
    if any("narrow" in warning or "opening" in warning for warning in warnings):
        return "Needs geometry edit: upper/opening too narrow"
    validation = _validation_by_key(detail)
    for key in ("bed_fit", "support_risk", "slice_success"):
        check = validation.get(key, {})
        if _state_tone(str(check.get("state", "review"))) != "pass":
            return "Needs geometry edit: upper/opening too narrow"
    return "None flagged"


def _next_action_label(detail: dict[str, Any]) -> str:
    verdict = _mapping(detail.get("print_verdict"))
    state = str(verdict.get("state", "review"))
    if _state_tone(state) == "fail":
        return "Fix the failed validation check, then rebuild this run."
    warnings = [str(warning).lower() for warning in _as_list(detail.get("warnings"))]
    if any("narrow" in warning or "opening" in warning for warning in warnings):
        return "Widen the upper/opening and rebuild from edits."
    support = _validation_by_key(detail).get("support_risk", {})
    if _state_tone(str(support.get("state", "review"))) == "warn":
        return "Choose a support strategy, then rebuild or inspect the slice receipt."
    if _state_tone(state) == "pass":
        return "Open the 3MF and inspect the slice receipt before printing."
    return "Inspect warnings, then either rebuild or open the current bundle."


def _signed_mm(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.0
    sign = "+" if number >= 0 else ""
    return f"{sign}{number:g} mm"


def _render_artifact_tiles(artifact_links: list[Any]) -> str:
    items = "\n".join(_render_primary_artifact_tile(label, categories, artifact_links) for label, categories in _PRIMARY_ARTIFACT_TILES)
    return "\n".join(
        [
            '              <div class="links">',
            items,
            "              </div>",
        ]
    )


_PRIMARY_ARTIFACT_TILES = (
    ("Original mesh", ("generated_mesh", "original_input")),
    ("Repaired mesh", ("repaired_mesh",)),
    ("Final STL", ("oriented_mesh",)),
    ("3MF", ("bundle",)),
    ("Slice report", ("reports", "slice_log")),
)


def _render_primary_artifact_tile(label: str, categories: tuple[str, ...], artifact_links: list[Any]) -> str:
    link = _first_artifact_link(categories, artifact_links)
    if link is None:
        return "\n".join(
            [
                '                <span class="missing-artifact">',
                f"                  <strong>{escape(label)}</strong>",
                "                  <span>Pending</span>",
                "                </span>",
            ]
        )
    path = str(getattr(link, "path", getattr(link, "download_name", "")))
    return "\n".join(
        [
            f'                <a href="{escape(str(getattr(link, "href", "#")), quote=True)}">',
            f"                  <strong>{escape(label)}</strong>",
            f"                  <span>{escape(path)}</span>",
            "                </a>",
        ]
    )


def _first_artifact_link(categories: tuple[str, ...], artifact_links: list[Any]) -> Any | None:
    for category in categories:
        for link in artifact_links:
            if str(getattr(link, "category", "")) == category:
                return link
    return None


def _print_readiness_checks(
    *,
    status: dict[str, Any],
    report: dict[str, Any],
    settings: dict[str, Any],
) -> list[dict[str, str]]:
    metrics = _combined_metrics(report)
    return [
        _readiness_manifold(metrics),
        _readiness_bed_fit(metrics),
        _readiness_profile(settings, metrics),
        _readiness_support(metrics, report),
        _readiness_slice(status, metrics),
    ]


def _readiness_manifold(metrics: dict[str, Any]) -> dict[str, str]:
    watertight = metrics.get("watertight")
    non_manifold_edges = metrics.get("non_manifold_edges")
    if watertight is True or non_manifold_edges == 0:
        return {"label": "Manifold / watertight", "state": "pass", "detail": "Mesh repair reports a watertight printable shell."}
    if watertight is False or _is_positive_number(non_manifold_edges):
        return {"label": "Manifold / watertight", "state": "fail", "detail": "Mesh has open or non-manifold geometry."}
    return {"label": "Manifold / watertight", "state": "review", "detail": "No mesh watertightness metric is available yet."}


def _readiness_bed_fit(metrics: dict[str, Any]) -> dict[str, str]:
    bed_fit = str(metrics.get("bed_fit") or metrics.get("bed_fit_status") or "").lower()
    if "fit" in bed_fit and "not" not in bed_fit and "fail" not in bed_fit:
        return {"label": "Bed fit", "state": "pass", "detail": "Oriented footprint fits the selected build plate."}
    if bed_fit:
        return {"label": "Bed fit", "state": "fail", "detail": f"Bed fit needs attention: {bed_fit}."}
    return {"label": "Bed fit", "state": "review", "detail": "No bed-fit verdict is available yet."}


def _readiness_profile(settings: dict[str, Any], metrics: dict[str, Any]) -> dict[str, str]:
    profile = metrics.get("profile") or settings.get("profile_label")
    printer = settings.get("printer_label") or settings.get("printer_id")
    material = settings.get("material_label") or settings.get("material_id")
    if profile or (printer and material):
        detail = " / ".join(str(value) for value in (printer, material, profile) if value)
        return {"label": "Material / profile sanity", "state": "pass", "detail": detail or "Profile inputs are present."}
    return {"label": "Material / profile sanity", "state": "review", "detail": "Printer/material/profile selection is incomplete."}


def _readiness_support(metrics: dict[str, Any], report: dict[str, Any]) -> dict[str, str]:
    risk = str(metrics.get("support_risk") or "").lower()
    warnings = [str(warning) for warning in report.get("warnings", []) if isinstance(warning, str)]
    if risk in {"none", "low"}:
        return {"label": "Support risk", "state": "pass", "detail": "Low support risk."}
    if risk in {"high", "fail", "failed"}:
        return {"label": "Support risk", "state": "fail", "detail": "High support risk; revise geometry or support strategy."}
    if risk:
        return {"label": "Support risk", "state": "review", "detail": f"{risk.title()} support risk; inspect overhangs."}
    if warnings:
        return {"label": "Support risk", "state": "review", "detail": warnings[0]}
    return {"label": "Support risk", "state": "review", "detail": "Support risk has not been classified yet."}


def _readiness_slice(status: dict[str, Any], metrics: dict[str, Any]) -> dict[str, str]:
    slice_success = metrics.get("slice_success")
    slice_stage = _matching_stage(("slice", "slice_report"), status.get("stages", []))
    stage_status = str(slice_stage.get("status", "")) if slice_stage else ""
    if slice_success is True or stage_status == "succeeded":
        return {"label": "Slice success", "state": "pass", "detail": "Bambu slice gate completed successfully."}
    if slice_success is False or stage_status == "failed":
        return {"label": "Slice success", "state": "fail", "detail": "Slice gate failed; inspect slicer logs."}
    return {"label": "Slice success", "state": "review", "detail": "Slice gate has not produced a success verdict yet."}


def _overall_readiness(checks: list[dict[str, str]]) -> str:
    states = {check["state"] for check in checks}
    if "fail" in states:
        return "Not print-ready yet. Fix the failed checks before sending to Bambu Studio."
    if "review" in states:
        return "Likely printable after review. Inspect warnings before committing filament."
    return "Ready to print from the available checks."


def _combined_metrics(report: dict[str, Any]) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for stage in _as_report_stages(report):
        stage_metrics = stage.get("metrics")
        if isinstance(stage_metrics, dict):
            metrics.update(stage_metrics)
    return metrics


def _matching_stage(aliases: tuple[str, ...], stages: Any) -> dict[str, Any] | None:
    if not isinstance(stages, list):
        return None
    normalized_aliases = {_class_name(alias) for alias in aliases}
    for stage in stages:
        if not isinstance(stage, dict):
            continue
        name = _class_name(str(stage.get("name") or stage.get("stage") or ""))
        if name in normalized_aliases or any(alias in name for alias in normalized_aliases):
            return stage
    return None


def _as_report_stages(report: dict[str, Any]) -> list[dict[str, Any]]:
    stages = report.get("stages")
    if not isinstance(stages, list):
        return []
    return [stage for stage in stages if isinstance(stage, dict)]


def _first_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                return item
    return value if isinstance(value, dict) else {}


def _setting_value(settings: dict[str, Any], key: str, default: str) -> str:
    value = settings.get(key, default)
    return "" if value is None else str(value)


def _field_value(mapping: dict[str, Any], key: str, default: str) -> str:
    value = mapping.get(key)
    return default if value is None else str(value)


def _checked(value: Any) -> str:
    return " checked" if bool(value) else ""


def _support_option(recipe: dict[str, Any], value: str, label: str) -> str:
    selected = " selected" if str(recipe.get("support_strategy", "auto")) == value else ""
    return (
        f'              <option value="{escape(value, quote=True)}"{selected}>'
        f"{escape(label)}"
        "</option>"
    )


def _detail_input_summary(detail: dict[str, Any]) -> str:
    input_info = _mapping(detail.get("input"))
    printer = _mapping(detail.get("printer"))
    material = _mapping(detail.get("material"))
    profile = _mapping(detail.get("profile"))
    parts = [
        f"Input: {input_info.get('kind', 'unknown')}",
        str(printer.get("label") or "Printer not selected"),
        str(material.get("label") or "Material not selected"),
        str(profile.get("label") or "Profile pending"),
    ]
    return " · ".join(parts)


def _input_summary(input_info: Any, settings: dict[str, Any]) -> str:
    if not isinstance(input_info, dict):
        input_info = {}
    parts = [
        f"Input: {input_info.get('kind', 'unknown')}",
        str(settings.get("printer_label") or settings.get("printer_id") or "Printer not selected"),
        str(settings.get("material_label") or settings.get("material_id") or "Material not selected"),
    ]
    return " · ".join(parts)


def _is_positive_number(value: Any) -> bool:
    return isinstance(value, int | float) and value > 0


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


_PIPELINE_STEPS = (
    ("Input / reference", ("input", "classify_input", "extract_references", "select_references", "route_existing_mesh")),
    ("Mesh generation", ("mesh_generation", "meshgen", "generated_mesh")),
    ("Repair", ("repair", "mesh_repair")),
    ("Orient / scale", ("orient_scale", "geometry", "bed_fit")),
    ("Print profile", ("print_profile", "profile", "profiles")),
    ("3MF bundle", ("bundle", "3mf")),
    ("Slice report", ("slice", "slice_report")),
)


_ARTIFACT_GROUPS = (
    ("bundle", "Downloads", ("bundle",)),
    ("preview", "Previews", ("preview",)),
    ("reports", "Reports", ("reports",)),
    ("mesh", "Inputs & Meshes", ("original_input", "generated_mesh", "repaired_mesh", "oriented_mesh")),
    ("logs", "Logs", ("slice_log",)),
)


def _render_artifact_groups(artifact_links: list[Any]) -> str:
    grouped: dict[str, list[Any]] = {}
    for link in artifact_links:
        grouped.setdefault(str(getattr(link, "category", "other")), []).append(link)

    sections: list[str] = []
    rendered_categories: set[str] = set()
    for group_id, heading, categories in _ARTIFACT_GROUPS:
        links = [
            link
            for category in categories
            for link in grouped.get(category, [])
        ]
        if not links:
            continue
        rendered_categories.update(categories)
        sections.append(_render_artifact_group(group_id, heading, links))

    remaining_links = [
        link
        for category, links in grouped.items()
        if category not in rendered_categories
        for link in links
    ]
    if remaining_links:
        sections.append(_render_artifact_group("other", "Other Artifacts", remaining_links))

    if not sections:
        return ""
    return '\n        <div class="artifact-groups">\n' + "\n".join(sections) + "\n        </div>"


def _render_artifact_group(group_id: str, heading: str, links: list[Any]) -> str:
    items = "\n".join(
        f"              <li>{_render_artifact_anchor(link)}</li>"
        for link in links
    )
    return "\n".join(
        [
            f'          <section class="artifact-group artifact-group-{_class_name(group_id)}">',
            f"            <h4>{escape(heading)}</h4>",
            '            <ul class="artifact-links">',
            items,
            "            </ul>",
            "          </section>",
        ]
    )


def _render_artifact_anchor(link: Any) -> str:
    label = str(getattr(link, "label", "Artifact"))
    href = str(getattr(link, "href", "#"))
    category = str(getattr(link, "category", "artifact"))
    download_name = str(getattr(link, "download_name", ""))
    media_type = str(getattr(link, "media_type", ""))
    is_bundle_download = (
        category == "bundle"
        and download_name.lower().endswith(".3mf")
        and media_type == "model/3mf"
    )
    download_attribute = (
        f' download="{escape(download_name, quote=True)}"'
        if is_bundle_download
        else ""
    )
    suffix = " .3mf" if is_bundle_download and ".3mf" not in label.lower() else ""
    return (
        f'<a href="{escape(href, quote=True)}"{download_attribute}>'
        f"{escape(label)}{suffix}"
        "</a>"
    )


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
    textarea,
    button {
      box-sizing: border-box;
      font: inherit;
      width: 100%;
    }
    input,
    select,
    textarea {
      border: 1px solid #bcccdc;
      border-radius: 6px;
      padding: 8px 10px;
    }
    input,
    select,
    button {
      min-height: 40px;
    }
    textarea {
      min-height: 96px;
      resize: vertical;
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
    button:disabled {
      background: #9fb3c8;
      cursor: not-allowed;
    }
    .run-detail-app {
      background:
        radial-gradient(circle at 10% 0%, rgba(50, 125, 158, 0.12), transparent 28rem),
        linear-gradient(135deg, #f6f8fb 0%, #eef2f5 58%, #e7edf2 100%);
      color: #17202a;
      max-width: none;
      min-height: 100vh;
      padding: 0 0 40px;
    }
    .topbar {
      align-items: center;
      backdrop-filter: blur(16px);
      background: rgba(249, 250, 251, 0.9);
      border-bottom: 1px solid #cfd8e3;
      display: grid;
      gap: 20px;
      grid-template-columns: minmax(0, 1fr) auto;
      margin: 0;
      padding: 18px clamp(18px, 3vw, 36px);
      position: sticky;
      top: 0;
      z-index: 5;
    }
    .topbar h1 {
      font-size: clamp(1.5rem, 2.3vw, 2.35rem);
      letter-spacing: 0;
      margin-bottom: 6px;
      word-break: break-word;
    }
    .eyebrow {
      color: #607080;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 0.72rem;
      font-weight: 800;
      letter-spacing: 0;
      margin: 0 0 6px;
      text-transform: uppercase;
    }
    .run-meta {
      color: #52606d;
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      font-size: 0.86rem;
    }
    .run-meta span {
      background: #ffffff;
      border: 1px solid #d9e2ec;
      border-radius: 999px;
      padding: 4px 8px;
    }
    .status-chip {
      align-self: center;
      border: 1px solid #b8c6d4;
      border-radius: 999px;
      font-weight: 850;
      padding: 9px 12px;
      white-space: nowrap;
    }
    .status-chip-pass {
      background: #e3f8ec;
      border-color: #a6d8ba;
      color: #126237;
    }
    .status-chip-warn {
      background: #fff4d6;
      border-color: #e7c36d;
      color: #7c4a03;
    }
    .status-chip-fail {
      background: #fde8e8;
      border-color: #e6a6a6;
      color: #9b1c1c;
    }
    .shell {
      display: grid;
      gap: 16px;
      margin: 0 auto;
      max-width: 1620px;
      padding: clamp(14px, 2vw, 24px);
    }
    .verdict-strip {
      display: grid;
      gap: 10px;
      grid-template-columns: 1.2fr repeat(5, minmax(110px, 1fr));
    }
    .verdict,
    .score,
    .model-card,
    .card,
    .controls {
      background: rgba(255, 255, 255, 0.94);
      border: 1px solid #cfd8e3;
      border-radius: 8px;
      box-shadow: 0 18px 46px rgba(36, 47, 61, 0.1);
    }
    .verdict {
      background: #17202a;
      color: #f8fafc;
      padding: 14px;
    }
    .verdict h2 {
      font-size: clamp(1.35rem, 2.1vw, 2rem);
      margin-bottom: 6px;
    }
    .verdict p:last-child {
      color: #d8e2ec;
      margin-bottom: 0;
    }
    .next-action {
      background: rgba(255, 255, 255, 0.08);
      border: 1px solid rgba(216, 226, 236, 0.22);
      border-radius: 8px;
      margin: 12px 0 0;
      padding: 9px 10px;
    }
    .next-action span {
      color: #9fb3c8;
      display: block;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 0.7rem;
      font-weight: 850;
      margin-bottom: 3px;
      text-transform: uppercase;
    }
    .score {
      padding: 14px;
    }
    .score span,
    .metric span {
      color: #607080;
      display: block;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 0.72rem;
      font-weight: 800;
      text-transform: uppercase;
    }
    .score strong,
    .metric strong {
      display: block;
      font-size: 1.18rem;
      margin-top: 6px;
      overflow-wrap: anywhere;
    }
    .score-pass strong {
      color: #126237;
    }
    .score-warn strong {
      color: #7c4a03;
    }
    .score-fail strong {
      color: #9b1c1c;
    }
    .workbench {
      display: grid;
      gap: clamp(14px, 2vw, 24px);
      grid-template-columns: minmax(0, 1fr) minmax(330px, 410px);
    }
    .canvas-zone {
      display: grid;
      gap: 14px;
      grid-template-rows: minmax(420px, auto) auto;
      min-width: 0;
    }
    .model-card {
      display: grid;
      grid-template-rows: auto minmax(420px, 1fr) auto auto;
      min-height: 520px;
      overflow: hidden;
    }
    .toolbar {
      align-items: center;
      border-bottom: 1px solid #cfd8e3;
      display: flex;
      gap: 10px;
      justify-content: space-between;
      padding: 12px 14px;
    }
    .view-tabs {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }
    .tab {
      background: #f8fafc;
      border: 1px solid #cfd8e3;
      border-radius: 999px;
      color: #52606d;
      font-size: 0.84rem;
      font-weight: 750;
      min-height: auto;
      padding: 7px 10px;
      width: auto;
    }
    .tab.active {
      background: #17202a;
      border-color: #17202a;
      color: #ffffff;
    }
    .model-view {
      align-items: center;
      background:
        linear-gradient(90deg, rgba(50, 125, 158, 0.12) 1px, transparent 1px),
        linear-gradient(rgba(50, 125, 158, 0.1) 1px, transparent 1px),
        radial-gradient(circle at 50% 44%, rgba(50, 125, 158, 0.13), transparent 34%),
        #f7fafc;
      background-size: 42px 42px, 42px 42px, auto, auto;
      display: grid;
      justify-items: center;
      margin: 0;
      overflow: hidden;
      position: relative;
    }
    .bed {
      background: rgba(255, 255, 255, 0.3);
      border: 2px solid rgba(50, 125, 158, 0.42);
      border-radius: 8px;
      bottom: 8%;
      height: min(48%, 430px);
      position: absolute;
      transform: perspective(920px) rotateX(62deg);
      width: min(82%, 860px);
    }
    .mesh-placeholder {
      aspect-ratio: 2.1;
      background:
        linear-gradient(90deg, rgba(255, 255, 255, 0.72) 0 1px, transparent 1px 22px),
        linear-gradient(rgba(255, 255, 255, 0.65) 0 1px, transparent 1px 22px),
        linear-gradient(135deg, rgba(50, 125, 158, 0.26), rgba(255, 255, 255, 0.54)),
        repeating-linear-gradient(24deg, rgba(23, 32, 42, 0.16) 0 1px, transparent 1px 19px);
      border: 3px solid rgba(23, 32, 42, 0.68);
      border-radius: 14px;
      box-shadow: 0 26px 65px rgba(23, 32, 42, 0.22);
      position: relative;
      transform: perspective(880px) rotateX(54deg) rotateZ(-4deg);
      width: min(54vw, 650px);
      z-index: 1;
    }
    .model-preview-image {
      display: block;
      max-height: 80%;
      max-width: 88%;
      object-fit: contain;
      position: relative;
      width: min(60vw, 760px);
      z-index: 1;
    }
    .mesh-placeholder::before,
    .mesh-placeholder::after {
      border: 2px solid rgba(23, 32, 42, 0.4);
      border-radius: 50%;
      content: "";
      position: absolute;
    }
    .mesh-placeholder::before {
      height: 42%;
      left: 13%;
      top: 25%;
      width: 24%;
    }
    .mesh-placeholder::after {
      height: 36%;
      right: 17%;
      top: 30%;
      width: 20%;
    }
    .risk-marker,
    .measure {
      background: rgba(255, 255, 255, 0.9);
      border: 1px dashed rgba(23, 32, 42, 0.5);
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 0.78rem;
      padding: 4px 7px;
      position: absolute;
      z-index: 2;
    }
    .risk-marker {
      border: 2px solid #c23030;
      color: #9b1c1c;
      font-weight: 900;
      right: 18%;
      top: 43%;
    }
    .measure-x {
      bottom: 15%;
      left: 19%;
    }
    .measure-z {
      right: 13%;
      top: 25%;
    }
    .preview-links {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      padding: 12px 14px;
    }
    .model-footer {
      background: #cfd8e3;
      border-top: 1px solid #cfd8e3;
      display: grid;
      gap: 1px;
      grid-template-columns: repeat(4, minmax(0, 1fr));
    }
    .metric {
      background: #ffffff;
      min-width: 0;
      padding: 12px;
    }
    .lower-grid {
      display: grid;
      gap: 14px;
      grid-template-columns: 1fr 1fr;
    }
    .card h2,
    .controls h2 {
      border-bottom: 1px solid #cfd8e3;
      font-size: 1rem;
      margin: 0;
      padding: 13px 14px;
    }
    .card-body,
    .controls-body {
      display: grid;
      gap: 13px;
      padding: 14px;
    }
    .stage-rail {
      display: grid;
      gap: 0;
    }
    .stage {
      align-items: start;
      border-bottom: 1px solid #e4e7eb;
      display: grid;
      gap: 10px;
      grid-template-columns: 18px minmax(0, 1fr) auto;
      padding: 9px 0;
    }
    .stage:last-child {
      border-bottom: 0;
    }
    .node {
      background: #b8c6d4;
      border-radius: 50%;
      height: 14px;
      margin-top: 3px;
      width: 14px;
    }
    .node-pass {
      background: #1f8a4c;
    }
    .node-warn {
      background: #b7791f;
    }
    .node-fail {
      background: #c23030;
    }
    .stage h3 {
      font-size: 0.92rem;
      margin: 0 0 2px;
    }
    .stage p {
      color: #52606d;
      font-size: 0.84rem;
      margin: 0;
    }
    .badge {
      align-self: start;
      border-radius: 999px;
      font-size: 0.7rem;
      font-weight: 900;
      padding: 4px 8px;
      text-transform: uppercase;
    }
    .badge-pass {
      background: #e3f8ec;
      color: #126237;
    }
    .badge-warn {
      background: #fff4d6;
      color: #7c4a03;
    }
    .badge-fail {
      background: #fde8e8;
      color: #9b1c1c;
    }
    .controls {
      align-self: start;
      margin: 0;
      overflow: hidden;
    }
    .control-grid {
      display: grid;
      gap: 10px;
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .input-card {
      border-left: 5px solid #327d9e;
      padding-left: 12px;
    }
    .input-card h3,
    .controls h3 {
      margin: 0 0 6px;
    }
    .input-card p {
      color: #52606d;
      margin-bottom: 6px;
    }
    .check-row {
      align-items: center;
      background: #f8fafc;
      border: 1px solid #cfd8e3;
      border-radius: 8px;
      color: #17202a;
      display: flex;
      gap: 8px;
      justify-content: space-between;
      padding: 10px;
      text-transform: none;
    }
    .check-row input {
      min-height: auto;
      width: auto;
    }
    .primary {
      background: #327d9e;
      max-width: none;
      width: 100%;
    }
    .edit-actions {
      background: linear-gradient(rgba(255, 255, 255, 0.86), #ffffff);
      bottom: 0;
      padding-top: 8px;
      position: sticky;
      z-index: 2;
    }
    .recipe-preview {
      background: #eef6f9;
      border: 1px solid #c6dfe9;
      border-radius: 8px;
      color: #24566d;
      margin: 0;
      padding: 10px;
    }
    .links {
      display: grid;
      gap: 8px;
      grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
    }
    .links a {
      background: #f8fafc;
      border: 1px solid #cfd8e3;
      border-radius: 8px;
      display: block;
      font-weight: 850;
      padding: 10px;
    }
    .links span {
      color: #52606d;
      display: block;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 0.72rem;
      margin-top: 4px;
      overflow-wrap: anywhere;
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
    .artifact-groups {
      display: grid;
      gap: 10px;
      margin-top: 12px;
    }
    .artifact-group {
      border-top: 1px solid #e4e7eb;
      padding-top: 10px;
    }
    .artifact-group h4 {
      color: #334e68;
      font-size: 0.84rem;
      margin: 0 0 6px;
      text-transform: uppercase;
    }
    progress {
      height: 10px;
      width: 100%;
    }
    .muted {
      color: #52606d;
    }
    .artifact-links {
      margin-top: 0;
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
    @media (max-width: 1180px) {
      .verdict-strip {
        grid-template-columns: repeat(3, minmax(0, 1fr));
      }
      .verdict {
        grid-column: 1 / -1;
      }
      .workbench {
        grid-template-columns: 1fr;
      }
      .controls {
        order: -1;
      }
    }
    @media (max-width: 760px) {
      .topbar,
      .verdict-strip,
      .lower-grid,
      .model-footer,
      .control-grid {
        grid-template-columns: 1fr;
      }
      .status-chip {
        white-space: normal;
      }
      .model-card {
        min-height: 430px;
      }
      .mesh-placeholder {
        width: 82vw;
      }
      .model-preview-image {
        width: 86vw;
      }
    }
""".strip()


__all__ = [
    "PrintPipeWebApp",
    "WebResponse",
    "create_app",
    "create_server",
    "serve",
]
