"""Dependency-free local web server helpers for PrintPipe."""

from __future__ import annotations

import json
import math
import mimetypes
import tempfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from email.parser import BytesParser
from email.policy import default as email_policy
from html import escape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlsplit

from printpipe.beta.readiness import build_beta_readiness_report
from printpipe.beta.physical_status import build_physical_validation_status
from printpipe.env.doctor import build_environment_report
from printpipe.local_open import open_run_folder
from printpipe.pipeline import (
    PipelineError,
    run_edit_recipe_pipeline,
    run_existing_mesh_pipeline,
    run_prompt_pipeline,
)
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
from printpipe.web.run_detail import render_run_detail_page
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
    upload: _UploadedFile | None
    prompt: str
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
        path_opener: Callable[[Path], object] | None = None,
    ) -> None:
        self.static_roots = tuple(Path(root) for root in static_roots)
        self.runs_dir = Path(runs_dir) if runs_dir is not None else None
        self.path_opener = path_opener

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
                relative_run_path = path.removeprefix(_RUNS_PREFIX)
                open_route = _open_folder_route(relative_run_path)
                if open_route is not None:
                    run_id, target = open_route
                    return self.open_folder_response(run_id, target)
                edit_run_id = _edit_route_id(relative_run_path)
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
        if path == "/doctor.json":
            return self.doctor_response()
        if path == "/readiness.json":
            return self.readiness_response()
        if path == "/physical-status.json":
            return self.physical_status_response()
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

    def open_folder_response(self, run_id: str, target: str) -> WebResponse:
        run_root = self._run_root(run_id)
        if run_root is None:
            return self.not_found_response()
        try:
            open_run_folder(run_root, target=target, path_opener=self.path_opener)
        except (FileNotFoundError, ValueError):
            return self.not_found_response()
        return WebResponse.redirect(f"/runs/{quote(run_id, safe='')}")

    def home_response(self) -> WebResponse:
        return WebResponse.html(self.render_home())

    def health_response(self) -> WebResponse:
        return WebResponse.json({"service": "printpipe-web", "status": "ok"})

    def doctor_response(self) -> WebResponse:
        try:
            return WebResponse.json(build_environment_report())
        except (OSError, ValueError) as exc:
            return WebResponse.from_text(
                f"{exc}\n",
                status=HTTPStatus.BAD_REQUEST,
                content_type=_TEXT_MEDIA_TYPE,
            )

    def readiness_response(self) -> WebResponse:
        if self.runs_dir is None:
            return WebResponse.from_text(
                "Runs directory is not configured.\n",
                status=HTTPStatus.SERVICE_UNAVAILABLE,
                content_type=_TEXT_MEDIA_TYPE,
            )
        try:
            return WebResponse.json(build_beta_readiness_report(self.runs_dir))
        except (OSError, ValueError) as exc:
            return WebResponse.from_text(
                f"{exc}\n",
                status=HTTPStatus.BAD_REQUEST,
                content_type=_TEXT_MEDIA_TYPE,
            )

    def physical_status_response(self) -> WebResponse:
        if self.runs_dir is None:
            return WebResponse.from_text(
                "Runs directory is not configured.\n",
                status=HTTPStatus.SERVICE_UNAVAILABLE,
                content_type=_TEXT_MEDIA_TYPE,
            )
        try:
            return WebResponse.json(build_physical_validation_status(self.runs_dir))
        except (OSError, ValueError) as exc:
            return WebResponse.from_text(
                f"{exc}\n",
                status=HTTPStatus.BAD_REQUEST,
                content_type=_TEXT_MEDIA_TYPE,
            )

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
            render_run_detail_page(
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
                self._render_physical_beta_gate_panel(),
                self._render_recent_runs_panel(),
                '    <section class="panel">',
                "      <h2>Service</h2>",
                '      <p><a href="/health">Health check</a></p>',
                '      <p><a href="/readiness.json">Readiness JSON</a></p>',
                '      <p><a href="/doctor.json">Environment doctor JSON</a></p>',
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
        prompt_image_provider_options = _render_select_options(
            (
                {
                    "id": "auto",
                    "label": "Auto",
                    "description": "Use a configured command first, then OpenAI when an API key is available.",
                },
                {
                    "id": "command",
                    "label": "Configured command",
                    "description": "Use PRINTPIPE_PROMPT_IMAGE_COMMAND.",
                },
                {
                    "id": "openai",
                    "label": "OpenAI",
                    "description": "Use the OpenAI Images API with OPENAI_API_KEY.",
                },
            ),
            selected_id="auto",
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
                "        <label>",
                "          <span>Prompt</span>",
                '          <textarea name="prompt" rows="3" placeholder="small ergonomic desk hook, wider TPU slipper upper, modular lamp shade"></textarea>',
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
                "            <span>Prompt image provider</span>",
                f'            <select name="prompt_image_provider">{prompt_image_provider_options}</select>',
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

    def _render_physical_beta_gate_panel(self) -> str:
        if self.runs_dir is None:
            return ""
        try:
            status = build_physical_validation_status(self.runs_dir)
        except (OSError, ValueError):
            return ""

        overall = str(status.get("overall_status", "unknown"))
        families = status.get("family_status")
        if not isinstance(families, dict):
            families = {}
        cards = "\n".join(
            self._render_physical_family_card(family, payload)
            for family, payload in sorted(families.items())
        )
        command = "printpipe physical-status --runs-dir runs --strict"
        return "\n".join(
            [
                '    <section class="panel physical-gate-panel">',
                "      <div>",
                "        <h2>Physical beta gate</h2>",
                f'        <p class="muted">Overall: <strong>{escape(overall)}</strong>. Digital artifacts do not count as physical proof.</p>',
                "      </div>",
                f'      <div class="physical-family-grid">{cards}</div>',
                f'      <code>{escape(command)}</code>',
                "    </section>",
            ]
        )

    def _render_physical_family_card(self, family: str, payload: Any) -> str:
        item = payload if isinstance(payload, dict) else {}
        state = str(item.get("status", "unknown"))
        reason = str(item.get("missing_reason") or "Physical evidence gate satisfied.")
        passed_count = str(item.get("passed_count", 0))
        packet_count = str(item.get("packet_count", 0))
        return "\n".join(
            [
                f'        <article class="physical-family physical-family-{_class_name(state)}">',
                f"          <span>{escape(family.upper())}</span>",
                f"          <strong>{escape(state)}</strong>",
                f"          <p>{escape(passed_count)} passed / {escape(packet_count)} packet(s)</p>",
                f'          <p class="muted">{escape(reason)}</p>',
                "        </article>",
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
        if form.upload is None:
            return self._create_prompt_skeleton_run(form)

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
                        prompt_hint=form.prompt or None,
                        prompt_image_provider=str(
                            form.launch_options.get("prompt_image_provider", "auto")
                        ),
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

    def _create_prompt_skeleton_run(self, form: _ParsedRunForm) -> RunLayout:
        runs_dir = Path(self.runs_dir).expanduser().resolve()
        try:
            result = run_prompt_pipeline(
                form.prompt,
                runs_dir,
                material=str(form.launch_options.get("material_id", "Unknown material")),
                printer=str(form.launch_options.get("printer_id", "Unknown printer")),
                use_case="web run",
                settings_changes=(form.launch_options,),
                prompt_image_provider=str(form.launch_options.get("prompt_image_provider", "auto")),
            )
        except PipelineError as exc:
            result = exc.result
        self._record_launch_options(result.layout, form.launch_options)
        return result.layout

    def _record_launch_options(self, layout: RunLayout, launch_options: dict[str, Any]) -> None:
        manifest = json.loads(layout.manifest_path.read_text(encoding="utf-8"))
        manifest["launch_options"] = launch_options
        layout.manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def create_app(
    static_roots: Iterable[str | Path] = (),
    *,
    runs_dir: str | Path | None = None,
    path_opener: Callable[[Path], object] | None = None,
) -> PrintPipeWebApp:
    """Create the local web app without binding a socket."""

    roots = [Path(root) for root in static_roots]
    if runs_dir is not None:
        roots.append(Path(runs_dir))
    return PrintPipeWebApp(static_roots=roots, runs_dir=runs_dir, path_opener=path_opener)


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
            if not filename and not payload:
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

    prompt = fields.get("prompt", "").strip()
    if upload is None and not prompt:
        raise _FormError(HTTPStatus.BAD_REQUEST, "Missing uploaded input file or prompt.")
    if upload is not None and not upload.content:
        raise _FormError(HTTPStatus.BAD_REQUEST, "Uploaded input file is empty.")

    return _ParsedRunForm(
        upload=upload,
        prompt=prompt,
        launch_options=_launch_options(
            fields,
            uploaded_filename=upload.filename if upload is not None else None,
        ),
    )


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


def _launch_options(fields: dict[str, str], uploaded_filename: str | None) -> dict[str, Any]:
    catalog = selector_catalog()
    defaults = catalog["defaults"]
    printer_id = fields.get("printer_id") or defaults["printer_id"]
    material_id = fields.get("material_id") or defaults["material_id"]
    prompt = fields.get("prompt", "").strip()
    prompt_image_provider = fields.get("prompt_image_provider") or "auto"

    printer_labels = {str(option.get("id", "")): str(option.get("label", "")) for option in catalog["printers"]}
    material_labels = {str(option.get("id", "")): str(option.get("label", "")) for option in catalog["materials"]}
    if printer_id not in printer_labels:
        raise _FormError(HTTPStatus.BAD_REQUEST, f"Unknown printer selection: {printer_id}.")
    if material_id not in material_labels:
        raise _FormError(HTTPStatus.BAD_REQUEST, f"Unknown material selection: {material_id}.")
    if prompt_image_provider not in {"auto", "command", "openai"}:
        raise _FormError(
            HTTPStatus.BAD_REQUEST,
            f"Unknown prompt image provider: {prompt_image_provider}.",
        )

    options: dict[str, Any] = {
        "source": "web_form",
        "input_mode": _input_mode(uploaded_filename=uploaded_filename, prompt=prompt),
        "prompt_image_provider": prompt_image_provider,
        "printer_id": printer_id,
        "printer_label": printer_labels[printer_id],
        "material_id": material_id,
        "material_label": material_labels[material_id],
    }
    if uploaded_filename is not None:
        options["uploaded_filename"] = _safe_upload_filename(uploaded_filename)
    if prompt:
        options["prompt"] = prompt
    target_fields = {
        field_name: _positive_float(fields[field_name], field_name=field_name)
        for field_name in _TARGET_SIZE_FIELDS
        if fields.get(field_name)
    }
    if not target_fields:
        target_fields["target_length_mm"] = 100.0
    options.update(target_fields)
    return options


def _input_mode(*, uploaded_filename: str | None, prompt: str) -> str:
    if uploaded_filename is None:
        return "prompt"
    if prompt:
        return "file+prompt"
    return "file"


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


def _open_folder_route(relative_url_path: str) -> tuple[str, str] | None:
    parts = unquote(relative_url_path).strip("/").split("/")
    if len(parts) != 3 or parts[1] != "open-folder":
        return None
    run_id, target = parts[0], parts[2]
    if not run_id or "/" in run_id or "\\" in run_id:
        return None
    if target not in {"run", "report", "bundle"}:
        return None
    return run_id, target



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
    .run-list,
    .physical-family-grid {
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
    .run-card {
      border: 1px solid #e4e7eb;
      border-radius: 8px;
      padding: 14px;
    }
    .physical-gate-panel {
      display: grid;
      gap: 14px;
    }
    .physical-gate-panel code {
      background: #f1f5f9;
      border: 1px solid #d9e2ec;
      border-radius: 6px;
      display: inline-block;
      font-size: 0.9rem;
      overflow-wrap: anywhere;
      padding: 8px 10px;
    }
    .physical-family {
      border: 1px solid #d9e2ec;
      border-radius: 8px;
      padding: 12px;
    }
    .physical-family span {
      color: #52606d;
      display: block;
      font-size: 0.78rem;
      font-weight: 800;
      letter-spacing: 0.04em;
      margin-bottom: 4px;
    }
    .physical-family strong {
      display: block;
      overflow-wrap: anywhere;
    }
    .physical-family p {
      margin: 6px 0 0;
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
""".strip()


__all__ = [
    "PrintPipeWebApp",
    "WebResponse",
    "create_app",
    "create_server",
    "serve",
]
