"""Dependency-free local web server helpers for PrintPipe."""

from __future__ import annotations

import json
import math
import mimetypes
import shlex
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

from printpipe.beta.beta_plan import build_beta_action_plan
from printpipe.beta.feedback import (
    FeedbackArtifact,
    build_trusted_user_feedback,
    build_trusted_user_feedback_plan,
    build_trusted_user_feedback_status,
    write_trusted_user_feedback_files,
)
from printpipe.beta.physical import (
    PhysicalArtifact,
    build_physical_print_evidence,
    write_physical_evidence_files,
)
from printpipe.beta.readiness import build_beta_readiness_report
from printpipe.beta.physical_plan import build_physical_validation_plan
from printpipe.beta.physical_start import start_physical_validation
from printpipe.beta.physical_status import build_physical_validation_status
from printpipe.config import (
    configured_media_meshgen_command,
    configured_media_meshgen_params,
    write_project_config,
)
from printpipe.env.doctor import build_environment_report
from printpipe.final_plan import build_final_action_plan, build_final_next_action_payload
from printpipe.web.final_readiness import (
    build_final_readiness_view,
    render_final_readiness_panel,
)
from printpipe.local_open import open_run_folder
from printpipe.meshgen.command_template import (
    available_media_meshgen_template_presets,
    write_media_meshgen_command_template,
)
from printpipe.meshgen.comfyui_workflow import inspect_comfyui_workflow
from printpipe.meshgen.smoke import build_media_meshgen_smoke_status
from printpipe.meshgen.smoke import run_media_meshgen_smoke
from printpipe.packaging.release_plan import (
    build_release_distribution_plan,
    start_release_distribution_handoff,
)
from printpipe.packaging.release_status import build_release_status_report
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


@dataclass(frozen=True)
class _ParsedPhysicalRecordForm:
    fields: dict[str, str]
    photo: _UploadedFile | None


@dataclass(frozen=True)
class _ParsedBetaFeedbackForm:
    fields: dict[str, str]
    artifact: _UploadedFile | None


@dataclass(frozen=True)
class _ParsedMediaSmokeForm:
    fields: dict[str, str]
    reference: _UploadedFile | None


@dataclass(frozen=True)
class _ParsedMediaWorkflowForm:
    fields: dict[str, str]
    workflow: _UploadedFile | None


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
        release_dir: str | Path | None = Path("dist/release"),
        regression_manifest_path: str | Path | None = None,
        path_opener: Callable[[Path], object] | None = None,
        workspace_dir: str | Path | None = None,
    ) -> None:
        self.static_roots = tuple(Path(root) for root in static_roots)
        self.runs_dir = Path(runs_dir) if runs_dir is not None else None
        self.release_dir = Path(release_dir) if release_dir is not None else None
        self.workspace_dir = Path(workspace_dir) if workspace_dir is not None else Path.cwd()
        self.regression_manifest_path = (
            Path(regression_manifest_path).expanduser()
            if regression_manifest_path is not None
            else None
        )
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
        split_target = urlsplit(target)
        path = split_target.path or "/"
        query = parse_qs(split_target.query, keep_blank_values=True)
        if request_method == "POST":
            if path == "/beta-feedback/record":
                return self.record_beta_feedback_response(headers=headers, body=body)
            if path == "/physical/record":
                return self.record_physical_response(headers=headers, body=body)
            if path == "/physical/start":
                return self.start_physical_response(headers=headers, body=body)
            if path == "/release/start":
                return self.start_release_response()
            if path == "/media-meshgen/template":
                return self.start_media_meshgen_template_response(headers=headers, body=body)
            if path == "/media-meshgen/comfyui-workflow":
                return self.configure_media_meshgen_comfyui_workflow_response(
                    headers=headers,
                    body=body,
                )
            if path == "/media-meshgen/configure":
                return self.configure_media_meshgen_response(headers=headers, body=body)
            if path == "/media-meshgen/smoke":
                return self.run_media_meshgen_smoke_response(headers=headers, body=body)
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
            return self.readiness_response(
                regression_manifest_path=self._regression_manifest_for_query(query)
            )
        if path == "/media-meshgen-smoke-status.json":
            return self.media_meshgen_smoke_status_response()
        if path == "/release-status.json":
            return self.release_status_response(
                regression_manifest_path=self._regression_manifest_for_query(query)
            )
        if path == "/release-plan.json":
            return self.release_plan_response(
                regression_manifest_path=self._regression_manifest_for_query(query)
            )
        if path == "/final-plan.json":
            return self.final_plan_response(
                regression_manifest_path=self._regression_manifest_for_query(query)
            )
        if path == "/final-next.json":
            return self.final_next_response(
                regression_manifest_path=self._regression_manifest_for_query(query)
            )
        if path == "/beta-plan.json":
            return self.beta_plan_response(
                regression_manifest_path=self._regression_manifest_for_query(query)
            )
        if path == "/beta-feedback-status.json":
            return self.beta_feedback_status_response()
        if path == "/beta-feedback-plan.json":
            return self.beta_feedback_plan_response()
        if path == "/physical-plan.json":
            return self.physical_plan_response()
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

    def start_release_response(self) -> WebResponse:
        if self.release_dir is None or self.runs_dir is None:
            return WebResponse.from_text(
                "Release directory or runs directory is not configured.\n",
                status=HTTPStatus.SERVICE_UNAVAILABLE,
                content_type=_TEXT_MEDIA_TYPE,
            )
        try:
            start_release_distribution_handoff(
                release_dir=self.release_dir,
                runs_dir=self.runs_dir,
                regression_manifest_path=self.regression_manifest_path,
            )
        except (OSError, ValueError) as exc:
            return WebResponse.from_text(
                f"{exc}\n",
                status=HTTPStatus.BAD_REQUEST,
                content_type=_TEXT_MEDIA_TYPE,
            )
        return WebResponse.redirect("/#release-distribution-plan")

    def start_media_meshgen_template_response(
        self,
        *,
        headers: Any | None,
        body: bytes,
    ) -> WebResponse:
        try:
            fields = _parse_edit_form(headers=headers, body=body) if body else {}
            preset = fields.get("preset", "generic")
            write_media_meshgen_command_template(
                self.workspace_dir / "scripts" / "media_meshgen_adapter.py",
                preset=preset,
            )
        except (OSError, ValueError, _FormError) as exc:
            message = exc.message if isinstance(exc, _FormError) else str(exc)
            return WebResponse.from_text(
                f"{message}\n",
                status=HTTPStatus.BAD_REQUEST,
                content_type=_TEXT_MEDIA_TYPE,
            )
        return WebResponse.redirect("/#media-meshgen-setup")

    def configure_media_meshgen_comfyui_workflow_response(
        self,
        *,
        headers: Any | None,
        body: bytes,
    ) -> WebResponse:
        try:
            form = _parse_media_workflow_form(headers=headers, body=body)
            if form.workflow is None or not form.workflow.content:
                raise _FormError(
                    HTTPStatus.BAD_REQUEST,
                    "ComfyUI workflow JSON upload is required.",
                )
            workflow_path = self.workspace_dir / "workflows" / _safe_upload_filename(
                form.workflow.filename
            )
            workflow_path.parent.mkdir(parents=True, exist_ok=True)
            workflow_path.write_bytes(form.workflow.content)
            report = inspect_comfyui_workflow(workflow_path)
            if report.get("status") != "ready":
                warnings = [
                    str(warning)
                    for warning in report.get("warnings", [])
                    if isinstance(warning, str) and warning
                ]
                detail = "\n".join(warnings) if warnings else "Workflow inspector returned action_required."
                raise _FormError(
                    HTTPStatus.BAD_REQUEST,
                    f"ComfyUI workflow is not ready for PrintPipe.\n{detail}",
                )
            write_media_meshgen_command_template(
                self.workspace_dir / "scripts" / "media_meshgen_adapter.py",
                preset="comfyui-api",
            )
            params = dict(report["suggested_params"])
            comfyui_url = form.fields.get("comfyui_url", "").strip()
            if comfyui_url:
                params["comfyui_url"] = comfyui_url
            command = (
                form.fields.get("command", "").strip()
                or "python scripts/media_meshgen_adapter.py"
            )
            write_project_config(
                updates={
                    "media_meshgen_command": command,
                    "media_meshgen_params": params,
                },
                cwd=self.workspace_dir,
            )
        except _FormError as exc:
            return WebResponse.from_text(
                f"{exc.message}\n",
                status=exc.status,
                content_type=_TEXT_MEDIA_TYPE,
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return WebResponse.from_text(
                f"{exc}\n",
                status=HTTPStatus.BAD_REQUEST,
                content_type=_TEXT_MEDIA_TYPE,
            )
        return WebResponse.redirect("/#media-meshgen-setup")

    def configure_media_meshgen_response(
        self,
        *,
        headers: Any | None,
        body: bytes,
    ) -> WebResponse:
        try:
            fields = _parse_edit_form(headers=headers, body=body)
            command = str(fields.get("command") or "").strip()
            if not command:
                raise _FormError(
                    HTTPStatus.BAD_REQUEST,
                    "Media meshgen command is required.",
                )
            write_project_config(
                updates={
                    "media_meshgen_command": command,
                    **_media_meshgen_config_updates_from_fields(fields),
                },
                cwd=self.workspace_dir,
            )
        except _FormError as exc:
            return WebResponse.from_text(
                f"{exc.message}\n",
                status=exc.status,
                content_type=_TEXT_MEDIA_TYPE,
            )
        except OSError as exc:
            return WebResponse.from_text(
                f"{exc}\n",
                status=HTTPStatus.BAD_REQUEST,
                content_type=_TEXT_MEDIA_TYPE,
            )
        return WebResponse.redirect("/#media-meshgen-setup")

    def run_media_meshgen_smoke_response(
        self,
        *,
        headers: Any | None,
        body: bytes,
    ) -> WebResponse:
        if self.runs_dir is None:
            return WebResponse.from_text(
                "Runs directory is not configured.\n",
                status=HTTPStatus.SERVICE_UNAVAILABLE,
                content_type=_TEXT_MEDIA_TYPE,
            )
        try:
            form = _parse_media_smoke_form(headers=headers, body=body)
            if form.reference is None or not form.reference.content:
                raise _FormError(
                    HTTPStatus.BAD_REQUEST,
                    "Media meshgen reference upload is required.",
                )
            command = configured_media_meshgen_command(cwd=self.workspace_dir)
            if not command:
                raise _FormError(
                    HTTPStatus.BAD_REQUEST,
                    "Media meshgen command is not configured.",
                )
            with tempfile.TemporaryDirectory() as temp_dir:
                reference_path = Path(temp_dir) / _safe_upload_filename(
                    form.reference.filename
                )
                reference_path.write_bytes(form.reference.content)
                run_media_meshgen_smoke(
                    reference_path,
                    runs_dir=self.runs_dir,
                    command=command,
                    output_format=_media_smoke_output_format(form.fields),
                    prompt=form.fields.get("prompt") or None,
                    config_cwd=self.workspace_dir,
                )
        except _FormError as exc:
            return WebResponse.from_text(
                f"{exc.message}\n",
                status=exc.status,
                content_type=_TEXT_MEDIA_TYPE,
            )
        except (OSError, ValueError) as exc:
            return WebResponse.from_text(
                f"{exc}\n",
                status=HTTPStatus.BAD_REQUEST,
                content_type=_TEXT_MEDIA_TYPE,
            )
        return WebResponse.redirect("/#media-meshgen-setup")

    def start_physical_response(self, *, headers: Any | None, body: bytes) -> WebResponse:
        if self.runs_dir is None:
            return WebResponse.from_text(
                "Runs directory is not configured.\n",
                status=HTTPStatus.SERVICE_UNAVAILABLE,
                content_type=_TEXT_MEDIA_TYPE,
            )

        try:
            fields = _parse_edit_form(headers=headers, body=body)
            family = fields.get("family", "").strip().lower()
            if family not in {"pla", "petg", "tpu"}:
                raise _FormError(
                    HTTPStatus.BAD_REQUEST,
                    "Physical validation family must be pla, petg, or tpu.",
                )
            start_physical_validation(
                self.runs_dir,
                family=family,
                operator=fields.get("operator", "").strip(),
            )
        except _FormError as exc:
            return WebResponse.from_text(
                f"{exc.message}\n",
                status=exc.status,
                content_type=_TEXT_MEDIA_TYPE,
            )
        except (OSError, ValueError) as exc:
            return WebResponse.from_text(
                f"{exc}\n",
                status=HTTPStatus.BAD_REQUEST,
                content_type=_TEXT_MEDIA_TYPE,
            )

        return WebResponse.redirect("/#physical-action-plan")

    def record_physical_response(self, *, headers: Any | None, body: bytes) -> WebResponse:
        if self.runs_dir is None:
            return WebResponse.from_text(
                "Runs directory is not configured.\n",
                status=HTTPStatus.SERVICE_UNAVAILABLE,
                content_type=_TEXT_MEDIA_TYPE,
            )

        try:
            form = _parse_physical_record_form(headers=headers, body=body)
            action = self._physical_record_action(form.fields.get("family", ""))
            run_root = self._physical_action_run_root(action)
            if form.photo is None or not form.photo.content:
                raise _FormError(HTTPStatus.BAD_REQUEST, "Physical evidence photo is required.")
            print_status = form.fields.get("print_status", "").strip().lower()
            if print_status not in {"passed", "failed", "partial"}:
                raise _FormError(
                    HTTPStatus.BAD_REQUEST,
                    "Physical print status must be passed, failed, or partial.",
                )
            with tempfile.TemporaryDirectory() as temp_dir:
                photo_path = Path(temp_dir) / _safe_upload_filename(form.photo.filename)
                photo_path.write_bytes(form.photo.content)
                evidence = build_physical_print_evidence(
                    run_id=run_root.name,
                    material=str(action.get("material_hint") or action.get("material") or ""),
                    printer="Bambu Lab P2S",
                    object_label=str(action.get("object_label") or ""),
                    print_type=str(action.get("print_type") or "coupon"),
                    print_status=print_status,
                    operator=form.fields.get("operator", "").strip(),
                    slice_status=form.fields.get("slice_status", "").strip(),
                    filament_drying=form.fields.get("filament_drying", "").strip(),
                    bed_prep=form.fields.get("bed_prep", "").strip(),
                    first_layer=form.fields.get("first_layer", "").strip(),
                    adhesion=form.fields.get("adhesion", "").strip(),
                    warping=form.fields.get("warping", "").strip(),
                    stringing=form.fields.get("stringing", "").strip(),
                    layer_bonding=form.fields.get("layer_bonding", "").strip(),
                    flex_recovery=form.fields.get("flex_recovery", "").strip(),
                    support_removal=form.fields.get("support_removal", "").strip(),
                    artifacts=(
                        PhysicalArtifact(
                            label="Physical print photo",
                            path=photo_path,
                            kind="photo",
                            notes="Uploaded from the local PrintPipe browser.",
                        ),
                    ),
                    notes=("Recorded from the local PrintPipe browser.",),
                )
                write_physical_evidence_files(
                    run_root=run_root,
                    evidence=evidence,
                    copy_artifacts=True,
                )
        except _FormError as exc:
            return WebResponse.from_text(
                f"{exc.message}\n",
                status=exc.status,
                content_type=_TEXT_MEDIA_TYPE,
            )
        except (OSError, ValueError) as exc:
            return WebResponse.from_text(
                f"{exc}\n",
                status=HTTPStatus.BAD_REQUEST,
                content_type=_TEXT_MEDIA_TYPE,
            )

        return WebResponse.redirect("/#physical-action-plan")

    def record_beta_feedback_response(
        self,
        *,
        headers: Any | None,
        body: bytes,
    ) -> WebResponse:
        if self.runs_dir is None:
            return WebResponse.from_text(
                "Runs directory is not configured.\n",
                status=HTTPStatus.SERVICE_UNAVAILABLE,
                content_type=_TEXT_MEDIA_TYPE,
            )

        try:
            form = _parse_beta_feedback_record_form(headers=headers, body=body)
            action = self._trusted_feedback_record_action(form.fields.get("slot", ""))
            run_root = self._trusted_feedback_action_run_root(action)
            summary = form.fields.get("summary", "").strip()
            if not summary:
                raise _FormError(
                    HTTPStatus.BAD_REQUEST,
                    "Trusted-user feedback summary is required.",
                )
            recommendation = form.fields.get("recommendation", "").strip()
            if not recommendation:
                raise _FormError(
                    HTTPStatus.BAD_REQUEST,
                    "Trusted-user recommendation is required.",
                )
            artifacts: tuple[FeedbackArtifact, ...] = ()
            with tempfile.TemporaryDirectory() as temp_dir:
                if form.artifact is not None and form.artifact.content:
                    artifact_path = Path(temp_dir) / _safe_upload_filename(
                        form.artifact.filename
                    )
                    artifact_path.write_bytes(form.artifact.content)
                    artifacts = (
                        FeedbackArtifact(
                            label="Trusted-user review artifact",
                            path=artifact_path,
                            kind="artifact",
                            notes="Uploaded from the local PrintPipe browser.",
                        ),
                    )
                feedback = build_trusted_user_feedback(
                    run_id=run_root.name,
                    tester=str(action.get("tester") or ""),
                    tester_type="trusted_user",
                    input_type=str(action.get("input_type") or "existing_stl"),
                    material=str(action.get("material") or ""),
                    printer=str(action.get("printer") or ""),
                    outcome=form.fields.get("outcome", "").strip(),
                    summary=summary,
                    issues=_feedback_issues_from_fields(form.fields),
                    would_print=form.fields.get("would_print", "").strip(),
                    recommendation=recommendation,
                    artifacts=artifacts,
                )
                write_trusted_user_feedback_files(
                    run_root=run_root,
                    feedback=feedback,
                    copy_artifacts=True,
                )
        except _FormError as exc:
            return WebResponse.from_text(
                f"{exc.message}\n",
                status=exc.status,
                content_type=_TEXT_MEDIA_TYPE,
            )
        except (OSError, ValueError) as exc:
            return WebResponse.from_text(
                f"{exc}\n",
                status=HTTPStatus.BAD_REQUEST,
                content_type=_TEXT_MEDIA_TYPE,
            )

        return WebResponse.redirect("/#trusted-user-action-plan")

    def home_response(self) -> WebResponse:
        return WebResponse.html(self.render_home())

    def _regression_manifest_for_query(self, query: dict[str, list[str]]) -> Path | None:
        return _query_path(query, "regression_manifest") or self.regression_manifest_path

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

    def readiness_response(
        self,
        *,
        regression_manifest_path: Path | None = None,
    ) -> WebResponse:
        if self.runs_dir is None:
            return WebResponse.from_text(
                "Runs directory is not configured.\n",
                status=HTTPStatus.SERVICE_UNAVAILABLE,
                content_type=_TEXT_MEDIA_TYPE,
            )
        try:
            manifest_path = regression_manifest_path or self.regression_manifest_path
            if manifest_path is None:
                return WebResponse.json(build_beta_readiness_report(self.runs_dir))
            return WebResponse.json(
                build_beta_readiness_report(
                    self.runs_dir,
                    regression_manifest_path=manifest_path,
                )
            )
        except (OSError, ValueError) as exc:
            return WebResponse.from_text(
                f"{exc}\n",
                status=HTTPStatus.BAD_REQUEST,
                content_type=_TEXT_MEDIA_TYPE,
            )

    def media_meshgen_smoke_status_response(self) -> WebResponse:
        if self.runs_dir is None:
            return WebResponse.from_text(
                "Runs directory is not configured.\n",
                status=HTTPStatus.SERVICE_UNAVAILABLE,
                content_type=_TEXT_MEDIA_TYPE,
            )
        try:
            return WebResponse.json(build_media_meshgen_smoke_status(self.runs_dir))
        except (OSError, ValueError) as exc:
            return WebResponse.from_text(
                f"{exc}\n",
                status=HTTPStatus.BAD_REQUEST,
                content_type=_TEXT_MEDIA_TYPE,
            )

    def release_status_response(
        self,
        *,
        regression_manifest_path: Path | None = None,
    ) -> WebResponse:
        if self.runs_dir is None or self.release_dir is None:
            return WebResponse.from_text(
                "Runs directory or release directory is not configured.\n",
                status=HTTPStatus.SERVICE_UNAVAILABLE,
                content_type=_TEXT_MEDIA_TYPE,
            )
        try:
            manifest_path = regression_manifest_path or self.regression_manifest_path
            if manifest_path is None:
                return WebResponse.json(
                    build_release_status_report(
                        release_dir=self.release_dir,
                        runs_dir=self.runs_dir,
                    )
                )
            return WebResponse.json(
                build_release_status_report(
                    release_dir=self.release_dir,
                    runs_dir=self.runs_dir,
                    regression_manifest_path=manifest_path,
                )
            )
        except (OSError, ValueError) as exc:
            return WebResponse.from_text(
                f"{exc}\n",
                status=HTTPStatus.BAD_REQUEST,
                content_type=_TEXT_MEDIA_TYPE,
            )

    def release_plan_response(
        self,
        *,
        regression_manifest_path: Path | None = None,
    ) -> WebResponse:
        if self.release_dir is None or self.runs_dir is None:
            return WebResponse.from_text(
                "Release and runs directories are not configured.\n",
                status=HTTPStatus.SERVICE_UNAVAILABLE,
                content_type=_TEXT_MEDIA_TYPE,
            )
        try:
            manifest_path = (
                regression_manifest_path
                if regression_manifest_path is not None
                else self.regression_manifest_path
            )
            return WebResponse.json(
                build_release_distribution_plan(
                    release_dir=self.release_dir,
                    runs_dir=self.runs_dir,
                    regression_manifest_path=manifest_path,
                )
            )
        except (OSError, ValueError) as exc:
            return WebResponse.from_text(
                f"{exc}\n",
                status=HTTPStatus.BAD_REQUEST,
                content_type=_TEXT_MEDIA_TYPE,
            )

    def final_plan_response(
        self,
        *,
        regression_manifest_path: Path | None = None,
    ) -> WebResponse:
        if self.release_dir is None or self.runs_dir is None:
            return WebResponse.from_text(
                "Release and runs directories are not configured.\n",
                status=HTTPStatus.SERVICE_UNAVAILABLE,
                content_type=_TEXT_MEDIA_TYPE,
            )
        try:
            manifest_path = (
                regression_manifest_path
                if regression_manifest_path is not None
                else self.regression_manifest_path
            )
            return WebResponse.json(
                build_final_action_plan(
                    release_dir=self.release_dir,
                    runs_dir=self.runs_dir,
                    regression_manifest_path=manifest_path,
                )
            )
        except (OSError, ValueError) as exc:
            return WebResponse.from_text(
                f"{exc}\n",
                status=HTTPStatus.BAD_REQUEST,
                content_type=_TEXT_MEDIA_TYPE,
            )

    def final_next_response(
        self,
        *,
        regression_manifest_path: Path | None = None,
    ) -> WebResponse:
        if self.release_dir is None or self.runs_dir is None:
            return WebResponse.from_text(
                "Release and runs directories are not configured.\n",
                status=HTTPStatus.SERVICE_UNAVAILABLE,
                content_type=_TEXT_MEDIA_TYPE,
            )
        try:
            manifest_path = (
                regression_manifest_path
                if regression_manifest_path is not None
                else self.regression_manifest_path
            )
            plan = build_final_action_plan(
                release_dir=self.release_dir,
                runs_dir=self.runs_dir,
                regression_manifest_path=manifest_path,
            )
            return WebResponse.json(build_final_next_action_payload(plan))
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

    def beta_feedback_status_response(self) -> WebResponse:
        if self.runs_dir is None:
            return WebResponse.from_text(
                "Runs directory is not configured.\n",
                status=HTTPStatus.SERVICE_UNAVAILABLE,
                content_type=_TEXT_MEDIA_TYPE,
            )
        try:
            return WebResponse.json(build_trusted_user_feedback_status(self.runs_dir))
        except (OSError, ValueError) as exc:
            return WebResponse.from_text(
                f"{exc}\n",
                status=HTTPStatus.BAD_REQUEST,
                content_type=_TEXT_MEDIA_TYPE,
            )

    def beta_feedback_plan_response(self) -> WebResponse:
        if self.runs_dir is None:
            return WebResponse.from_text(
                "Runs directory is not configured.\n",
                status=HTTPStatus.SERVICE_UNAVAILABLE,
                content_type=_TEXT_MEDIA_TYPE,
            )
        try:
            return WebResponse.json(build_trusted_user_feedback_plan(self.runs_dir))
        except (OSError, ValueError) as exc:
            return WebResponse.from_text(
                f"{exc}\n",
                status=HTTPStatus.BAD_REQUEST,
                content_type=_TEXT_MEDIA_TYPE,
            )

    def physical_plan_response(self) -> WebResponse:
        if self.runs_dir is None:
            return WebResponse.from_text(
                "Runs directory is not configured.\n",
                status=HTTPStatus.SERVICE_UNAVAILABLE,
                content_type=_TEXT_MEDIA_TYPE,
            )
        try:
            return WebResponse.json(build_physical_validation_plan(self.runs_dir))
        except (OSError, ValueError) as exc:
            return WebResponse.from_text(
                f"{exc}\n",
                status=HTTPStatus.BAD_REQUEST,
                content_type=_TEXT_MEDIA_TYPE,
            )

    def beta_plan_response(
        self,
        *,
        regression_manifest_path: Path | None = None,
    ) -> WebResponse:
        if self.runs_dir is None:
            return WebResponse.from_text(
                "Runs directory is not configured.\n",
                status=HTTPStatus.SERVICE_UNAVAILABLE,
                content_type=_TEXT_MEDIA_TYPE,
            )
        try:
            manifest_path = regression_manifest_path or self.regression_manifest_path
            if manifest_path is None:
                return WebResponse.json(build_beta_action_plan(self.runs_dir))
            return WebResponse.json(
                build_beta_action_plan(
                    self.runs_dir,
                    regression_manifest_path=manifest_path,
                )
            )
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
                self._render_final_action_plan_panel(),
                self._render_release_status_panel(),
                self._render_release_distribution_plan_panel(),
                self._render_readiness_panel(),
                self._render_media_meshgen_setup_panel(),
                self._render_media_meshgen_smoke_status_panel(),
                self._render_physical_beta_gate_panel(),
                self._render_physical_action_plan_panel(),
                self._render_trusted_feedback_gate_panel(),
                self._render_trusted_feedback_action_plan_panel(),
                self._render_beta_action_plan_panel(),
                self._render_recent_runs_panel(),
                '    <section class="panel">',
                "      <h2>Service</h2>",
                '      <p><a href="/health">Health check</a></p>',
                f'      <p><a href="{escape(self._service_href("/final-plan.json"), quote=True)}">Final plan JSON</a></p>',
                f'      <p><a href="{escape(self._service_href("/release-status.json"), quote=True)}">Release status JSON</a></p>',
                f'      <p><a href="{escape(self._service_href("/release-plan.json"), quote=True)}">Release plan JSON</a></p>',
                f'      <p><a href="{escape(self._service_href("/readiness.json"), quote=True)}">Readiness JSON</a></p>',
                '      <p><a href="/media-meshgen-smoke-status.json">Media meshgen smoke JSON</a></p>',
                '      <p><a href="/physical-plan.json">Physical plan JSON</a></p>',
                '      <p><a href="/beta-feedback-status.json">Trusted-user feedback JSON</a></p>',
                '      <p><a href="/beta-feedback-plan.json">Trusted-user feedback plan JSON</a></p>',
                f'      <p><a href="{escape(self._service_href("/beta-plan.json"), quote=True)}">Beta plan JSON</a></p>',
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

    def _render_readiness_panel(self) -> str:
        if self.runs_dir is None:
            return ""
        try:
            if self.regression_manifest_path is None:
                report = build_beta_readiness_report(self.runs_dir)
            else:
                report = build_beta_readiness_report(
                    self.runs_dir,
                    regression_manifest_path=self.regression_manifest_path,
                )
        except (OSError, ValueError):
            return ""
        overall = str(report.get("overall_status", "unknown"))
        action_count = str(report.get("action_required_count", 0))
        gates = _as_dicts(report.get("gates"))
        gate_cards = "\n".join(self._render_readiness_gate(gate) for gate in gates)
        return "\n".join(
            [
                '    <section class="panel readiness-panel">',
                "      <div>",
                "        <h2>Readiness gates</h2>",
                f'        <p class="muted">Overall: <strong>{escape(overall)}</strong>; {escape(action_count)} action required.</p>',
                "      </div>",
                f'      <div class="readiness-grid">{gate_cards}</div>',
                "    </section>",
            ]
        )

    def _render_media_meshgen_smoke_status_panel(self) -> str:
        if self.runs_dir is None:
            return ""
        try:
            status = build_media_meshgen_smoke_status(self.runs_dir)
        except (OSError, ValueError):
            return ""

        overall = str(status.get("overall_status") or "unknown")
        message = str(status.get("message") or "No media meshgen smoke status recorded.")
        action = str(status.get("action") or "No action recorded.")
        latest_value = status.get("latest_successful_smoke")
        latest = latest_value if isinstance(latest_value, dict) else {}
        latest_label = str(latest.get("run_id") or "none")
        provider = str(latest.get("provider_id") or "none")
        output_path = str(latest.get("output_path") or "none")
        return "\n".join(
            [
                '    <section class="panel readiness-panel media-smoke-panel">',
                "      <div>",
                "        <h2>Media meshgen smoke</h2>",
                f'        <p class="muted">overall: {escape(overall)}</p>',
                "      </div>",
                '      <div class="readiness-grid">',
                f'        <article class="readiness-gate readiness-gate-{_class_name(overall)}">',
                "          <span>Smoke receipts</span>",
                f"          <strong>{escape(str(status.get('successful_smoke_count', 0)))} successful</strong>",
                f"          <p>{escape(message)}</p>",
                f'          <p class="muted">{escape(action)}</p>',
                "        </article>",
                f'        <article class="readiness-gate readiness-gate-{_class_name(overall)}">',
                "          <span>Latest successful smoke</span>",
                f"          <strong>{escape(latest_label)}</strong>",
                f"          <p>Provider: {escape(provider)}</p>",
                f'          <p class="muted">Output: {escape(output_path)}</p>',
                "        </article>",
                "      </div>",
                '      <p class="muted"><a href="/media-meshgen-smoke-status.json">Media meshgen smoke JSON</a></p>',
                "    </section>",
            ]
        )

    def _render_media_meshgen_setup_panel(self) -> str:
        current_command = configured_media_meshgen_command(cwd=self.workspace_dir)
        current_params = configured_media_meshgen_params(cwd=self.workspace_dir)
        template_path = self.workspace_dir / "scripts" / "media_meshgen_adapter.py"
        preset_options = "".join(
            f'<option value="{escape(preset, quote=True)}">{escape(_media_template_preset_label(preset))}</option>'
            for preset in available_media_meshgen_template_presets()
        )
        current_markup = (
            f"Current saved command: <code>{escape(current_command)}</code>"
            if current_command
            else "No media meshgen command saved in project config."
        )
        return "\n".join(
            [
                '    <section id="media-meshgen-setup" class="panel media-meshgen-setup-panel">',
                "      <div>",
                "        <h2>Media meshgen setup</h2>",
                "        <p>This does not prove semantic reconstruction. Create or point at a real adapter, then run a smoke test.</p>",
                f'        <p class="muted">{current_markup}</p>',
                "      </div>",
                '      <div class="readiness-grid">',
                '        <article class="readiness-gate readiness-gate-action-required">',
                "          <span>Adapter template</span>",
                f"          <p>Writes <code>{escape(str(template_path))}</code>.</p>",
                '          <form method="post" action="/media-meshgen/template">',
                '            <label for="media-template-preset">Preset</label>',
                (
                    '            <select id="media-template-preset" name="preset">'
                    f"{preset_options}</select>"
                ),
                '            <button type="submit">Create adapter template</button>',
                "          </form>",
                "        </article>",
                '        <article class="readiness-gate readiness-gate-action-required">',
                "          <span>ComfyUI workflow</span>",
                "          <p>Upload an exported API workflow to inspect and save patch paths.</p>",
                '          <form method="post" action="/media-meshgen/comfyui-workflow" enctype="multipart/form-data">',
                '            <label for="media-comfyui-workflow-upload">Workflow JSON</label>',
                '            <input id="media-comfyui-workflow-upload" name="workflow" type="file" accept="application/json,.json">',
                '            <label for="media-comfyui-upload-command">Command</label>',
                (
                    '            <input id="media-comfyui-upload-command" name="command" '
                    'type="text" placeholder="python scripts/media_meshgen_adapter.py" '
                    f'value="{escape(current_command or "python scripts/media_meshgen_adapter.py", quote=True)}">'
                ),
                '            <label for="media-comfyui-upload-url">ComfyUI URL</label>',
                (
                    '            <input id="media-comfyui-upload-url" name="comfyui_url" '
                    'type="text" placeholder="http://127.0.0.1:8188" '
                    f'value="{escape(str(current_params.get("comfyui_url", "")), quote=True)}">'
                ),
                '            <button type="submit">Inspect and save workflow</button>',
                "          </form>",
                "        </article>",
                '        <article class="readiness-gate readiness-gate-action-required">',
                "          <span>Project command</span>",
                '          <form method="post" action="/media-meshgen/configure">',
                '            <label for="media-meshgen-command">Command</label>',
                (
                    '            <input id="media-meshgen-command" name="command" '
                    'type="text" placeholder="python scripts/media_meshgen_adapter.py" '
                    f'value="{escape(current_command, quote=True)}">'
                ),
                '            <label for="media-comfyui-url">ComfyUI URL</label>',
                (
                    '            <input id="media-comfyui-url" name="comfyui_url" '
                    'type="text" placeholder="http://127.0.0.1:8188" '
                    f'value="{escape(str(current_params.get("comfyui_url", "")), quote=True)}">'
                ),
                '            <label for="media-comfyui-workflow">ComfyUI workflow JSON</label>',
                (
                    '            <input id="media-comfyui-workflow" name="comfyui_workflow" '
                    'type="text" placeholder="workflows/image_to_glb.json" '
                    f'value="{escape(str(current_params.get("comfyui_workflow", "")), quote=True)}">'
                ),
                '            <label for="media-comfyui-image-paths">Image patch paths</label>',
                (
                    '            <input id="media-comfyui-image-paths" name="comfyui_image_paths" '
                    'type="text" placeholder="12.inputs.image" '
                    f'value="{escape(_comma_join_param(current_params.get("comfyui_image_paths")), quote=True)}">'
                ),
                '            <label for="media-comfyui-prompt-paths">Prompt patch paths</label>',
                (
                    '            <input id="media-comfyui-prompt-paths" name="comfyui_prompt_paths" '
                    'type="text" placeholder="6.inputs.text" '
                    f'value="{escape(_comma_join_param(current_params.get("comfyui_prompt_paths")), quote=True)}">'
                ),
                '            <label for="media-comfyui-seed-paths">Seed patch paths</label>',
                (
                    '            <input id="media-comfyui-seed-paths" name="comfyui_seed_paths" '
                    'type="text" placeholder="3.inputs.seed" '
                    f'value="{escape(_comma_join_param(current_params.get("comfyui_seed_paths")), quote=True)}">'
                ),
                (
                    '            <label><input name="comfyui_allow_no_source_patch" type="checkbox" value="1"'
                    f'{_checked(bool(current_params.get("comfyui_allow_no_source_patch")))}> '
                    "Prompt-only workflow has no image patch</label>"
                ),
                '            <label for="media-params-json">Extra params JSON</label>',
                (
                    '            <textarea id="media-params-json" name="params_json" '
                    'placeholder=\'{"model_version":"..."}\'></textarea>'
                ),
                '            <button type="submit">Save media command</button>',
                "          </form>",
                "        </article>",
                '        <article class="readiness-gate readiness-gate-action-required">',
                "          <span>Smoke test</span>",
                '          <form method="post" action="/media-meshgen/smoke" enctype="multipart/form-data">',
                '            <label for="media-smoke-reference">Reference image/GIF/video</label>',
                '            <input id="media-smoke-reference" name="reference" type="file" accept="image/*,video/*,.gif">',
                '            <label for="media-smoke-prompt">Prompt hint</label>',
                '            <input id="media-smoke-prompt" name="prompt" type="text" placeholder="printable desk hook">',
                '            <label for="media-smoke-output-format">Output format</label>',
                '            <select id="media-smoke-output-format" name="output_format">',
                '              <option value="stl">STL</option>',
                '              <option value="glb">GLB</option>',
                '              <option value="obj">OBJ</option>',
                '            </select>',
                '            <button type="submit">Run media smoke</button>',
                "          </form>",
                "        </article>",
                "      </div>",
                "      <p class=\"muted\">After replacing the template with a real provider, run: "
                "<code>printpipe media-meshgen-smoke reference.png --runs-dir runs --output-format glb</code></p>",
                "    </section>",
            ]
        )

    def _render_final_action_plan_panel(self) -> str:
        if self.release_dir is None or self.runs_dir is None:
            return ""
        try:
            if self.regression_manifest_path is None:
                plan = build_final_action_plan(
                    release_dir=self.release_dir,
                    runs_dir=self.runs_dir,
                )
            else:
                plan = build_final_action_plan(
                    release_dir=self.release_dir,
                    runs_dir=self.runs_dir,
                    regression_manifest_path=self.regression_manifest_path,
                )
            physical_status = build_physical_validation_status(self.runs_dir)
            feedback_status = build_trusted_user_feedback_status(self.runs_dir)
        except (OSError, ValueError):
            return ""

        view = build_final_readiness_view(
            plan,
            physical_status=physical_status,
            feedback_status=feedback_status,
        )
        return render_final_readiness_panel(view)

    def _render_final_action_section_card(self, section: dict[str, Any]) -> str:
        status = str(section.get("status", "unknown"))
        label = str(section.get("label") or section.get("id") or "Final action")
        detail = str(section.get("detail") or "Final action required.")
        action_count = str(section.get("action_count", 0))
        command = str(section.get("command") or "")
        return "\n".join(
            [
                f'        <article class="physical-action physical-action-{_class_name(status)}">',
                f"          <span>{escape(label)}</span>",
                f"          <strong>{escape(status)}</strong>",
                f"          <p>{escape(detail)}</p>",
                f'          <p class="muted">{escape(action_count)} action required.</p>',
                f"          <pre><code>{escape(command)}</code></pre>",
                "        </article>",
            ]
        )

    def _render_release_status_panel(self) -> str:
        if self.runs_dir is None or self.release_dir is None:
            return ""
        try:
            if self.regression_manifest_path is None:
                report = build_release_status_report(
                    release_dir=self.release_dir,
                    runs_dir=self.runs_dir,
                )
            else:
                report = build_release_status_report(
                    release_dir=self.release_dir,
                    runs_dir=self.runs_dir,
                    regression_manifest_path=self.regression_manifest_path,
                )
        except (OSError, ValueError):
            return ""
        overall = str(report.get("overall_status", "unknown"))
        action_count = str(report.get("action_required_count", 0))
        gates = _as_dicts(report.get("gates"))
        gate_cards = "\n".join(self._render_readiness_gate(gate) for gate in gates)
        return "\n".join(
            [
                '    <section class="panel readiness-panel">',
                "      <div>",
                "        <h2>Release status</h2>",
                f'        <p class="muted">Overall: <strong>{escape(overall)}</strong>; {escape(action_count)} action required.</p>',
                "      </div>",
                f'      <div class="readiness-grid">{gate_cards}</div>',
                "    </section>",
            ]
        )

    def _render_readiness_gate(self, gate: dict[str, Any]) -> str:
        status = str(gate.get("status", "unknown"))
        return "\n".join(
            [
                f'        <article class="readiness-gate readiness-gate-{_class_name(status)}">',
                f"          <span>{escape(str(gate.get('label') or gate.get('id') or 'Gate'))}</span>",
                f"          <strong>{escape(status)}</strong>",
                f"          <p>{escape(str(gate.get('detail') or 'No detail recorded.'))}</p>",
                f'          <p class="muted">{escape(str(gate.get("action") or "No action recorded."))}</p>',
                "        </article>",
            ]
        )

    def _render_release_distribution_plan_panel(self) -> str:
        if self.release_dir is None or self.runs_dir is None:
            return ""
        try:
            if self.regression_manifest_path is None:
                plan = build_release_distribution_plan(
                    release_dir=self.release_dir,
                    runs_dir=self.runs_dir,
                )
            else:
                plan = build_release_distribution_plan(
                    release_dir=self.release_dir,
                    runs_dir=self.runs_dir,
                    regression_manifest_path=self.regression_manifest_path,
                )
        except (OSError, ValueError):
            return ""

        overall = str(plan.get("overall_status", "unknown"))
        action_count = str(plan.get("action_count", 0))
        proof_boundary = str(plan.get("proof_boundary", ""))
        actions = _as_dicts(plan.get("actions"))
        action_cards = "\n".join(
            self._render_release_distribution_action_card(action)
            for action in actions
        )
        if not action_cards:
            action_cards = '<p class="muted">No release distribution actions required.</p>'
        command = "printpipe release-plan --release-dir dist/release --runs-dir runs"
        if self.regression_manifest_path is not None:
            manifest_arg = shlex.quote(str(self.regression_manifest_path))
            command += f" --regression-manifest {manifest_arg}"
        return "\n".join(
            [
                '    <section id="release-distribution-plan" class="panel release-plan-panel">',
                "      <div>",
                "        <h2>Release distribution plan</h2>",
                f'        <p class="muted">Overall: <strong>{escape(overall)}</strong>; {escape(action_count)} action required.</p>',
                f"        <p>{escape(proof_boundary)}</p>",
                self._render_release_distribution_start_form(actions),
                "      </div>",
                f'      <div class="physical-action-grid">{action_cards}</div>',
                f'      <code>{escape(command)}</code>',
                "    </section>",
            ]
        )

    def _render_release_distribution_start_form(
        self,
        actions: list[dict[str, Any]],
    ) -> str:
        if not any(str(action.get("start_command") or "") for action in actions):
            return ""
        return "\n".join(
            [
                '        <form method="post" action="/release/start">',
                '          <button type="submit">Create release handoff</button>',
                "        </form>",
            ]
        )

    def _render_release_distribution_action_card(self, action: dict[str, Any]) -> str:
        status = str(action.get("status", "unknown"))
        label = str(action.get("label") or action.get("id") or "Release action")
        detail = str(action.get("detail") or "Release distribution action required.")
        required = action.get("required_inputs")
        required_text = (
            ", ".join(str(item) for item in required)
            if isinstance(required, list)
            else ""
        )
        required_markup = (
            f'          <p class="muted">Required inputs: {escape(required_text)}</p>'
            if required_text
            else ""
        )
        setup = str(action.get("setup_command") or "")
        start = str(action.get("start_command") or "")
        handoff = str(action.get("handoff_markdown_path") or "")
        command = str(action.get("command") or "")
        followup = str(action.get("followup_command") or "")
        setup_markup = (
            "\n".join(
                [
                    '          <p class="muted"><strong>Setup prerequisite:</strong></p>',
                    f"          <pre><code>{escape(setup)}</code></pre>",
                ]
            )
            if setup
            else ""
        )
        start_markup = (
            "\n".join(
                [
                    '          <p class="muted"><strong>Release handoff:</strong></p>',
                    f"          <pre><code>{escape(start)}</code></pre>",
                ]
            )
            if start
            else ""
        )
        handoff_markup = (
            "          <p class=\"muted\">Handoff: "
            f"<code>{escape(handoff)}</code></p>"
            if handoff
            else ""
        )
        command_markup = (
            "\n".join(
                [
                    '          <p class="muted"><strong>Build/check:</strong></p>',
                    f"          <pre><code>{escape(command)}</code></pre>",
                ]
            )
            if command
            else ""
        )
        followup_markup = (
            "\n".join(
                [
                    '          <p class="muted"><strong>Follow-up check:</strong></p>',
                    f"          <pre><code>{escape(followup)}</code></pre>",
                ]
            )
            if followup
            else ""
        )
        return "\n".join(
            [
                f'        <article class="physical-action physical-action-{_class_name(status)}">',
                f"          <span>{escape(label)}</span>",
                f"          <strong>{escape(status)}</strong>",
                f"          <p>{escape(detail)}</p>",
                required_markup,
                setup_markup,
                start_markup,
                handoff_markup,
                command_markup,
                followup_markup,
                "        </article>",
            ]
        )

    def _service_href(self, path: str) -> str:
        if self.regression_manifest_path is None:
            return path
        encoded_manifest = quote(str(self.regression_manifest_path), safe="")
        return f"{path}?regression_manifest={encoded_manifest}"

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

    def _render_physical_action_plan_panel(self) -> str:
        if self.runs_dir is None:
            return ""
        try:
            plan = build_physical_validation_plan(self.runs_dir)
        except (OSError, ValueError):
            return ""

        overall = str(plan.get("overall_status", "unknown"))
        action_count = str(plan.get("action_count", 0))
        proof_boundary = str(plan.get("proof_boundary", ""))
        actions = _as_dicts(plan.get("actions"))
        action_cards = "\n".join(
            self._render_physical_action_card(action)
            for action in actions
        )
        if not action_cards:
            action_cards = '<p class="muted">No physical validation actions required.</p>'
        command = "printpipe physical-plan --runs-dir runs"
        return "\n".join(
            [
                '    <section id="physical-action-plan" class="panel physical-plan-panel">',
                "      <div>",
                "        <h2>Physical action plan</h2>",
                f'        <p class="muted">Overall: <strong>{escape(overall)}</strong>; {escape(action_count)} action required.</p>',
                f"        <p>{escape(proof_boundary)}</p>",
                "      </div>",
                f'      <div class="physical-action-grid">{action_cards}</div>',
                f'      <code>{escape(command)}</code>',
                "    </section>",
            ]
        )

    def _render_physical_action_card(self, action: dict[str, Any]) -> str:
        family = str(action.get("family", "unknown")).upper()
        status = str(action.get("status", "unknown"))
        reason = str(action.get("reason") or "Physical evidence action required.")
        required = action.get("required_fields")
        required_text = (
            ", ".join(str(item) for item in required)
            if isinstance(required, list)
            else ""
        )
        setup_command = str(action.get("setup_command") or "")
        setup_markup = (
            "\n".join(
                [
                    '          <p class="muted"><strong>Setup:</strong></p>',
                    f"          <pre><code>{escape(setup_command)}</code></pre>",
                ]
            )
            if setup_command
            else ""
        )
        start_command = str(action.get("start_command") or "")
        start_form_markup = self._physical_start_form(action) if start_command else ""
        start_markup = (
            "\n".join(
                [
                    '          <p class="muted"><strong>Start packet:</strong></p>',
                    f"          <pre><code>{escape(start_command)}</code></pre>",
                ]
            )
            if start_command
            else ""
        )
        handoff_command = str(action.get("command") or "")
        handoff_command_markup = (
            "\n".join(
                [
                    '          <p class="muted"><strong>Print handoff:</strong></p>',
                    f"          <pre><code>{escape(handoff_command)}</code></pre>",
                ]
            )
            if handoff_command
            else ""
        )
        slice_command = str(action.get("slice_command") or "")
        slice_command_markup = (
            "\n".join(
                [
                    '          <p class="muted"><strong>Slice if needed:</strong></p>',
                    f"          <pre><code>{escape(slice_command)}</code></pre>",
                ]
            )
            if slice_command
            else ""
        )
        record_command = str(action.get("record_command") or "")
        record_form_markup = self._physical_record_form(action) if record_command else ""
        record_command_markup = (
            "\n".join(
                [
                    '          <p class="muted"><strong>Record after print:</strong></p>',
                    f"          <pre><code>{escape(record_command)}</code></pre>",
                ]
            )
            if record_command
            else ""
        )
        context = self._physical_action_context(action)
        context_markup = (
            f'          <p class="muted">Physical context: {escape(context)}</p>'
            if context
            else ""
        )
        file_markup = self._physical_action_files(action)
        return "\n".join(
            [
                f'        <article class="physical-action physical-action-{_class_name(status)}">',
                f"          <span>{escape(family)}</span>",
                f"          <strong>{escape(status)}</strong>",
                f"          <p>{escape(reason)}</p>",
                context_markup,
                f'          <p class="muted">Required: {escape(required_text or "not recorded")}</p>',
                file_markup,
                setup_markup,
                start_form_markup,
                start_markup,
                handoff_command_markup,
                slice_command_markup,
                record_form_markup,
                record_command_markup,
                "        </article>",
            ]
        )

    def _physical_action_context(self, action: dict[str, Any]) -> str:
        pairs = (
            ("material_hint", "Material"),
            ("material", "Material"),
            ("object_label", "Object"),
            ("print_type", "Print type"),
            ("run_root", "Run"),
        )
        seen_labels: set[str] = set()
        parts: list[str] = []
        for key, label in pairs:
            value = str(action.get(key) or "")
            if not value or label in seen_labels:
                continue
            seen_labels.add(label)
            parts.append(f"{label}: {value}")
        return "; ".join(parts)

    def _physical_action_files(self, action: dict[str, Any]) -> str:
        rows: list[str] = []
        for key, label in (
            ("coupon_stl_path", "Coupon artifact"),
            ("coupon_json_path", "Coupon sidecar"),
            ("bundle_path", "Bundle"),
            ("bundle_validation_path", "Bundle validation"),
            ("slice_result_path", "Slice receipt"),
            ("handoff_markdown_path", "Handoff"),
        ):
            value = str(action.get(key) or "")
            if value:
                rows.append(
                    f'          <p class="muted">{escape(label)}: '
                    f"{escape(value)}</p>"
                )
        return "\n".join(rows)

    def _physical_start_form(self, action: dict[str, Any]) -> str:
        family = str(action.get("family", "")).strip().lower()
        if family not in {"pla", "petg", "tpu"}:
            return ""
        return "\n".join(
            [
                '          <form method="post" action="/physical/start">',
                f'            <input type="hidden" name="family" value="{escape(family, quote=True)}">',
                '            <input type="hidden" name="operator" value="Zohar">',
                "            <button type=\"submit\">Create starter packet</button>",
                "          </form>",
            ]
        )

    def _physical_record_form(self, action: dict[str, Any]) -> str:
        family = str(action.get("family", "")).strip().lower()
        if family not in {"pla", "petg", "tpu"}:
            return ""
        if not str(action.get("handoff_markdown_path") or ""):
            return ""
        material_fields = _physical_record_fields_for_family(family)
        field_markup = "\n".join(
            f'            <label><span>{escape(label)}</span>'
            f'<input name="{escape(name, quote=True)}"></label>'
            for name, label in material_fields
        )
        return "\n".join(
            [
                '          <form class="physical-record-form" method="post" action="/physical/record" enctype="multipart/form-data">',
                f'            <input type="hidden" name="family" value="{escape(family, quote=True)}">',
                '            <input type="hidden" name="operator" value="Zohar">',
                '            <label><span>Print status</span><select name="print_status"><option value="passed">Passed</option><option value="partial">Partial</option><option value="failed">Failed</option></select></label>',
                '            <label><span>Photo</span><input type="file" name="photo" accept="image/*" required></label>',
                field_markup,
                '            <button type="submit">Record physical evidence</button>',
                "          </form>",
            ]
        )

    def _physical_record_action(self, family: str) -> dict[str, Any]:
        normalized = family.strip().lower()
        if normalized not in {"pla", "petg", "tpu"}:
            raise _FormError(
                HTTPStatus.BAD_REQUEST,
                "Physical validation family must be pla, petg, or tpu.",
            )
        if self.runs_dir is None:
            raise _FormError(HTTPStatus.SERVICE_UNAVAILABLE, "Runs directory is not configured.")
        plan = build_physical_validation_plan(
            self.runs_dir,
            required_families=(normalized,),
        )
        actions = _as_dicts(plan.get("actions"))
        for action in actions:
            if str(action.get("family") or "").lower() == normalized:
                return action
        raise _FormError(
            HTTPStatus.BAD_REQUEST,
            "Physical validation family already has passed evidence or no starter packet is required.",
        )

    def _physical_action_run_root(self, action: dict[str, Any]) -> Path:
        if self.runs_dir is None:
            raise _FormError(HTTPStatus.SERVICE_UNAVAILABLE, "Runs directory is not configured.")
        runs_root = self.runs_dir.expanduser().resolve()
        run_root = Path(str(action.get("run_root") or "")).expanduser().resolve()
        if not _is_relative_to(run_root, runs_root):
            raise _FormError(HTTPStatus.BAD_REQUEST, "Physical run folder is outside runs dir.")
        if not run_root.is_dir():
            raise _FormError(
                HTTPStatus.BAD_REQUEST,
                "Physical starter packet must exist before recording evidence.",
            )
        return run_root

    def _render_trusted_feedback_gate_panel(self) -> str:
        if self.runs_dir is None:
            return ""
        try:
            status = build_trusted_user_feedback_status(self.runs_dir)
        except (OSError, ValueError):
            return ""

        overall = str(status.get("overall_status", "unknown"))
        current = str(status.get("unique_trusted_user_count", 0))
        required = str(status.get("required_trusted_user_count", 0))
        packet_count = str(status.get("packet_count", 0))
        missing = str(status.get("missing_trusted_user_count", 0))
        users = status.get("trusted_users")
        user_names = ", ".join(str(user) for user in users) if isinstance(users, list) else ""
        not_run_users = status.get("not_run_trusted_users")
        not_run_names = (
            ", ".join(str(user) for user in not_run_users)
            if isinstance(not_run_users, list)
            else ""
        )
        outcome_counts = status.get("outcome_counts")
        positive_outcome_counts = (
            {
                key: value
                for key, value in outcome_counts.items()
                if _positive_count(value)
            }
            if isinstance(outcome_counts, dict)
            else {}
        )
        if positive_outcome_counts:
            outcome_text = ", ".join(
                f"{key}: {value}"
                for key, value in sorted(positive_outcome_counts.items())
            )
            outcome_status = "recorded"
        else:
            outcome_text = "No completed tester outcomes recorded."
            outcome_status = "missing"
        command = "printpipe beta-feedback-status --runs-dir runs --strict"
        cards = "\n".join(
            [
                self._render_trusted_feedback_card(
                    label="Trusted users",
                    status=overall,
                    detail=f"{current} / {required} trusted users",
                    note=f"Feedback packets: {packet_count}; missing: {missing}.",
                ),
                self._render_trusted_feedback_card(
                    label="Tester names",
                    status="recorded" if user_names else "missing",
                    detail=user_names or "No trusted users recorded.",
                    note="Internal and coordinator notes do not count toward this gate.",
                ),
                self._render_trusted_feedback_card(
                    label="Not-run testers",
                    status="audit_only" if not_run_names else "none",
                    detail=not_run_names or "No trusted users recorded as not-run.",
                    note="Not-run packets are audit records, not completed beta feedback.",
                ),
                self._render_trusted_feedback_card(
                    label="Outcomes",
                    status=outcome_status,
                    detail=outcome_text,
                    note="Feedback is separate from physical print proof.",
                ),
            ]
        )
        return "\n".join(
            [
                '    <section class="panel feedback-gate-panel">',
                "      <div>",
                "        <h2>Trusted-user feedback</h2>",
                f'        <p class="muted">Overall: <strong>{escape(overall)}</strong>; {escape(current)} / {escape(required)} trusted users.</p>',
                "      </div>",
                f'      <div class="physical-family-grid">{cards}</div>',
                f'      <code>{escape(command)}</code>',
                "    </section>",
            ]
        )

    def _render_trusted_feedback_card(
        self,
        *,
        label: str,
        status: str,
        detail: str,
        note: str,
    ) -> str:
        return "\n".join(
            [
                f'        <article class="physical-family physical-family-{_class_name(status)}">',
                f"          <span>{escape(label)}</span>",
                f"          <strong>{escape(status)}</strong>",
                f"          <p>{escape(detail)}</p>",
                f'          <p class="muted">{escape(note)}</p>',
                "        </article>",
            ]
        )

    def _render_trusted_feedback_action_plan_panel(self) -> str:
        if self.runs_dir is None:
            return ""
        try:
            plan = build_trusted_user_feedback_plan(self.runs_dir)
        except (OSError, ValueError):
            return ""

        overall = str(plan.get("overall_status", "unknown"))
        action_count = str(plan.get("action_count", 0))
        proof_boundary = str(plan.get("proof_boundary", ""))
        actions = _as_dicts(plan.get("actions"))
        action_cards = "\n".join(
            self._render_trusted_feedback_action_card(action)
            for action in actions
        )
        if not action_cards:
            action_cards = '<p class="muted">No trusted-user feedback actions required.</p>'
        command = "printpipe beta-feedback-plan --runs-dir runs"
        return "\n".join(
            [
                '    <section id="trusted-user-action-plan" class="panel feedback-plan-panel">',
                "      <div>",
                "        <h2>Trusted-user action plan</h2>",
                f'        <p class="muted">Overall: <strong>{escape(overall)}</strong>; {escape(action_count)} action required.</p>',
                f"        <p>{escape(proof_boundary)}</p>",
                "      </div>",
                f'      <div class="physical-action-grid">{action_cards}</div>',
                f'      <code>{escape(command)}</code>',
                "    </section>",
            ]
        )

    def _render_trusted_feedback_action_card(self, action: dict[str, Any]) -> str:
        slot = str(action.get("slot", "?"))
        status = str(action.get("status", "unknown"))
        detail = str(action.get("detail") or "Trusted-user feedback action required.")
        review_command = str(action.get("command") or "")
        record_command = str(action.get("record_command") or "")
        record_form_markup = self._trusted_feedback_record_form(action) if record_command else ""
        context = self._trusted_feedback_action_context(action)
        context_markup = (
            f'          <p class="muted">Review context: {escape(context)}</p>'
            if context
            else ""
        )
        file_markup = self._trusted_feedback_action_files(action)
        review_command_markup = (
            "\n".join(
                [
                    '          <p class="muted"><strong>Review handoff:</strong></p>',
                    f"          <pre><code>{escape(review_command)}</code></pre>",
                ]
            )
            if review_command and review_command != record_command
            else ""
        )
        record_command_markup = (
            "\n".join(
                [
                    '          <p class="muted"><strong>Record after review:</strong></p>',
                    f"          <pre><code>{escape(record_command)}</code></pre>",
                ]
            )
            if record_command
            else ""
        )
        return "\n".join(
            [
                f'        <article class="physical-action physical-action-{_class_name(status)}">',
                f"          <span>Tester slot {escape(slot)}</span>",
                f"          <strong>{escape(status)}</strong>",
                f"          <p>{escape(detail)}</p>",
                context_markup,
                file_markup,
                review_command_markup,
                record_form_markup,
                record_command_markup,
                "        </article>",
            ]
        )

    def _trusted_feedback_action_context(self, action: dict[str, Any]) -> str:
        pairs = (
            ("material_hint", "Material"),
            ("material", "Material"),
            ("printer", "Printer"),
            ("input_type", "Input"),
            ("tester", "Tester"),
            ("run_root", "Run"),
        )
        seen_labels: set[str] = set()
        parts: list[str] = []
        for key, label in pairs:
            value = str(action.get(key) or "")
            if not value or label in seen_labels:
                continue
            seen_labels.add(label)
            parts.append(f"{label}: {value}")
        return "; ".join(parts)

    def _trusted_feedback_action_files(self, action: dict[str, Any]) -> str:
        rows: list[str] = []
        for key, label in (
            ("handoff_markdown_path", "Handoff"),
            ("report_path", "Run report"),
            ("bundle_path", "Bundle"),
        ):
            value = str(action.get(key) or "")
            if value:
                rows.append(
                    f'          <p class="muted">{escape(label)}: '
                    f"{escape(value)}</p>"
                )
        return "\n".join(rows)

    def _trusted_feedback_record_form(self, action: dict[str, Any]) -> str:
        run_root = str(action.get("run_root") or "")
        handoff = str(action.get("handoff_markdown_path") or "")
        if not run_root or not handoff:
            return ""
        slot = str(action.get("slot") or "")
        return "\n".join(
            [
                '          <form class="trusted-feedback-record-form" method="post" action="/beta-feedback/record" enctype="multipart/form-data">',
                f'            <input type="hidden" name="slot" value="{escape(slot, quote=True)}">',
                '            <label><span>Outcome</span><select name="outcome"><option value="passed">Passed</option><option value="partial">Partial</option><option value="failed">Failed</option><option value="not_run">Not run</option></select></label>',
                '            <label><span>Summary</span><textarea name="summary"></textarea></label>',
                '            <label><span>Would print?</span><select name="would_print"><option value="yes">Yes</option><option value="no">No</option><option value="unknown">Unknown</option></select></label>',
                '            <label><span>Recommendation</span><input name="recommendation"></label>',
                '            <label><span>Issue</span><input name="issue"></label>',
                '            <label><span>Artifact</span><input type="file" name="artifact"></label>',
                '            <button type="submit">Record trusted feedback</button>',
                "          </form>",
            ]
        )

    def _trusted_feedback_record_action(self, slot: str) -> dict[str, Any]:
        try:
            parsed_slot = int(slot)
        except ValueError as exc:
            raise _FormError(HTTPStatus.BAD_REQUEST, "Trusted-user slot is required.") from exc
        if self.runs_dir is None:
            raise _FormError(HTTPStatus.SERVICE_UNAVAILABLE, "Runs directory is not configured.")
        plan = build_trusted_user_feedback_plan(self.runs_dir)
        for action in _as_dicts(plan.get("actions")):
            if int(action.get("slot") or 0) == parsed_slot:
                if not str(action.get("run_root") or ""):
                    raise _FormError(
                        HTTPStatus.BAD_REQUEST,
                        "Trusted-user handoff must exist before browser feedback can be recorded.",
                    )
                return action
        raise _FormError(
            HTTPStatus.BAD_REQUEST,
            "Trusted-user slot is already complete or unavailable.",
        )

    def _trusted_feedback_action_run_root(self, action: dict[str, Any]) -> Path:
        if self.runs_dir is None:
            raise _FormError(HTTPStatus.SERVICE_UNAVAILABLE, "Runs directory is not configured.")
        runs_root = self.runs_dir.expanduser().resolve()
        run_root = Path(str(action.get("run_root") or "")).expanduser().resolve()
        if not _is_relative_to(run_root, runs_root):
            raise _FormError(HTTPStatus.BAD_REQUEST, "Trusted-user run folder is outside runs dir.")
        if not run_root.is_dir():
            raise _FormError(
                HTTPStatus.BAD_REQUEST,
                "Trusted-user handoff run folder must exist before recording feedback.",
            )
        return run_root

    def _render_beta_action_plan_panel(self) -> str:
        if self.runs_dir is None:
            return ""
        try:
            if self.regression_manifest_path is None:
                plan = build_beta_action_plan(self.runs_dir)
            else:
                plan = build_beta_action_plan(
                    self.runs_dir,
                    regression_manifest_path=self.regression_manifest_path,
                )
        except (OSError, ValueError):
            return ""

        overall = str(plan.get("overall_status", "unknown"))
        action_count = str(plan.get("action_required_count", 0))
        proof_boundary = str(plan.get("proof_boundary", ""))
        actions = _as_dicts(plan.get("actions"))
        action_cards = "\n".join(
            self._render_beta_action_card(action)
            for action in actions
        )
        if not action_cards:
            action_cards = '<p class="muted">No beta actions required.</p>'
        command = "printpipe beta-plan --runs-dir runs"
        if self.regression_manifest_path is not None:
            manifest_arg = shlex.quote(str(self.regression_manifest_path))
            command += f" --regression-manifest {manifest_arg}"
        return "\n".join(
            [
                '    <section class="panel beta-plan-panel">',
                "      <div>",
                "        <h2>Beta action plan</h2>",
                f'        <p class="muted">Overall: <strong>{escape(overall)}</strong>; {escape(action_count)} action required.</p>',
                f"        <p>{escape(proof_boundary)}</p>",
                "      </div>",
                f'      <div class="beta-action-grid">{action_cards}</div>',
                f'      <code>{escape(command)}</code>',
                "    </section>",
            ]
        )

    def _render_beta_action_card(self, action: dict[str, Any]) -> str:
        action_id = str(action.get("id", "unknown"))
        label = str(action.get("label") or action_id)
        status = str(action.get("status", "unknown"))
        detail = str(action.get("detail") or "No detail recorded.")
        command = str(action.get("command") or "")
        command_markup = (
            f"          <pre><code>{escape(command)}</code></pre>"
            if command
            else ""
        )
        return "\n".join(
            [
                f'        <article class="beta-action beta-action-{_class_name(status)}">',
                f"          <span>{escape(action_id)}</span>",
                f"          <strong>{escape(label)}</strong>",
                f"          <p>{escape(status)}</p>",
                f'          <p class="muted">{escape(detail)}</p>',
                command_markup,
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
        artifact_links = self._run_artifact_links(run_id)
        print_verdict = self._render_run_card_print_verdict(run_id, artifact_links)
        artifacts = _render_artifact_groups(artifact_links)

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
                print_verdict,
                f"          {workbench_link}",
                f"          {report_link}",
                f"{artifacts}",
                "        </article>",
            ]
        )

    def _render_run_card_print_verdict(
        self,
        run_id: str,
        artifact_links: list[Any],
    ) -> str:
        if not _has_bundle_download(artifact_links):
            return ""
        run_root = self._run_root(run_id)
        if run_root is None:
            return ""
        try:
            detail = build_run_detail(run_root)
        except (OSError, json.JSONDecodeError, ValueError):
            return ""

        verdict = detail.get("print_verdict")
        if not isinstance(verdict, dict):
            return ""
        state = str(verdict.get("state") or "review")
        label = str(verdict.get("label") or "Review before print")
        reason = str(verdict.get("reason") or "Open the workbench before printing.")
        return "\n".join(
            [
                (
                    "          "
                    f'<section class="run-print-verdict run-print-verdict-{_class_name(state)}">'
                ),
                "            <span>Print decision</span>",
                f"            <strong>{escape(label)}</strong>",
                f"            <p>{escape(reason)}</p>",
                '            <p class="muted">Open the workbench and inspect the bundle before sending this print.</p>',
                "          </section>",
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
    release_dir: str | Path | None = Path("dist/release"),
    regression_manifest_path: str | Path | None = None,
    path_opener: Callable[[Path], object] | None = None,
    workspace_dir: str | Path | None = None,
) -> PrintPipeWebApp:
    """Create the local web app without binding a socket."""

    roots = [Path(root) for root in static_roots]
    if runs_dir is not None:
        roots.append(Path(runs_dir))
    return PrintPipeWebApp(
        static_roots=roots,
        runs_dir=runs_dir,
        release_dir=release_dir,
        regression_manifest_path=regression_manifest_path,
        path_opener=path_opener,
        workspace_dir=workspace_dir,
    )


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
    regression_manifest_path: str | Path | None = None,
) -> None:
    """Run the local server until interrupted."""

    web_app = app or create_app(
        runs_dir=runs_dir,
        regression_manifest_path=regression_manifest_path,
    )
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


def _parse_physical_record_form(
    *,
    headers: Any | None,
    body: bytes,
) -> _ParsedPhysicalRecordForm:
    if len(body) > _MAX_FORM_BODY_BYTES:
        raise _FormError(
            HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            "Physical evidence upload is too large.",
        )

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
    photo: _UploadedFile | None = None
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
            if field_name != "photo":
                continue
            if not filename and not payload:
                continue
            if len(payload) > _MAX_UPLOAD_BYTES:
                raise _FormError(
                    HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                    "Physical evidence photo is too large.",
                )
            photo = _UploadedFile(
                field_name=field_name,
                filename=filename,
                content_type=part.get_content_type(),
                content=payload,
            )
            continue

        if len(payload) > _MAX_FIELD_CHARS * 4:
            raise _FormError(HTTPStatus.BAD_REQUEST, f"Form field is too long: {field_name}.")
        fields[field_name] = payload.decode(part.get_content_charset() or "utf-8", "replace").strip()

    return _ParsedPhysicalRecordForm(fields=fields, photo=photo)


def _parse_beta_feedback_record_form(
    *,
    headers: Any | None,
    body: bytes,
) -> _ParsedBetaFeedbackForm:
    if len(body) > _MAX_FORM_BODY_BYTES:
        raise _FormError(
            HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            "Trusted-user feedback upload is too large.",
        )

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
    artifact: _UploadedFile | None = None
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
            if field_name != "artifact":
                continue
            if not filename and not payload:
                continue
            if len(payload) > _MAX_UPLOAD_BYTES:
                raise _FormError(
                    HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                    "Trusted-user feedback artifact is too large.",
                )
            artifact = _UploadedFile(
                field_name=field_name,
                filename=filename,
                content_type=part.get_content_type(),
                content=payload,
            )
            continue

        if len(payload) > _MAX_FIELD_CHARS * 4:
            raise _FormError(HTTPStatus.BAD_REQUEST, f"Form field is too long: {field_name}.")
        fields[field_name] = payload.decode(part.get_content_charset() or "utf-8", "replace").strip()

    return _ParsedBetaFeedbackForm(fields=fields, artifact=artifact)


def _parse_media_smoke_form(
    *,
    headers: Any | None,
    body: bytes,
) -> _ParsedMediaSmokeForm:
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
    reference: _UploadedFile | None = None
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
            if field_name != "reference":
                continue
            if not filename and not payload:
                continue
            if len(payload) > _MAX_UPLOAD_BYTES:
                raise _FormError(
                    HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                    "Uploaded reference is too large.",
                )
            reference = _UploadedFile(
                field_name=field_name,
                filename=filename,
                content_type=part.get_content_type(),
                content=payload,
            )
            continue

        if len(payload) > _MAX_FIELD_CHARS:
            raise _FormError(HTTPStatus.BAD_REQUEST, f"Form field is too long: {field_name}.")
        fields[field_name] = payload.decode(part.get_content_charset() or "utf-8", "replace").strip()

    return _ParsedMediaSmokeForm(fields=fields, reference=reference)


def _parse_media_workflow_form(
    *,
    headers: Any | None,
    body: bytes,
) -> _ParsedMediaWorkflowForm:
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
    workflow: _UploadedFile | None = None
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
            if field_name != "workflow":
                continue
            if not filename and not payload:
                continue
            if len(payload) > _MAX_UPLOAD_BYTES:
                raise _FormError(
                    HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                    "Uploaded workflow is too large.",
                )
            workflow = _UploadedFile(
                field_name=field_name,
                filename=filename,
                content_type=part.get_content_type(),
                content=payload,
            )
            continue

        if len(payload) > _MAX_FIELD_CHARS:
            raise _FormError(HTTPStatus.BAD_REQUEST, f"Form field is too long: {field_name}.")
        fields[field_name] = payload.decode(part.get_content_charset() or "utf-8", "replace").strip()

    return _ParsedMediaWorkflowForm(fields=fields, workflow=workflow)


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


def _physical_record_fields_for_family(family: str) -> tuple[tuple[str, str], ...]:
    if family == "tpu":
        return (
            ("filament_drying", "Filament drying"),
            ("layer_bonding", "Layer bonding"),
            ("flex_recovery", "Flex recovery"),
            ("adhesion", "Adhesion"),
        )
    if family == "petg":
        return (
            ("first_layer", "First layer"),
            ("adhesion", "Adhesion"),
            ("warping", "Warping"),
            ("stringing", "Stringing"),
        )
    return (
        ("first_layer", "First layer"),
        ("adhesion", "Adhesion"),
    )


def _feedback_issues_from_fields(fields: dict[str, str]) -> tuple[str, ...]:
    issue = fields.get("issue", "").strip()
    return (issue,) if issue else ()


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


def _media_template_preset_label(preset: str) -> str:
    if preset == "comfyui-api":
        return "ComfyUI API / SaveGLB"
    return "Generic Python adapter"


def _media_smoke_output_format(fields: dict[str, str]) -> str:
    output_format = fields.get("output_format", "stl").strip().lower() or "stl"
    if output_format not in {"stl", "glb", "obj"}:
        raise _FormError(
            HTTPStatus.BAD_REQUEST,
            "Media smoke output format must be stl, glb, or obj.",
        )
    return output_format


def _media_meshgen_config_updates_from_fields(fields: dict[str, str]) -> dict[str, Any]:
    raw_params = fields.get("params_json", "").strip()
    params = _json_object_form_field(raw_params) if raw_params else {}
    params.update(_comfyui_params_from_fields(fields))
    return {"media_meshgen_params": params} if params else {}


def _comfyui_params_from_fields(fields: dict[str, str]) -> dict[str, Any]:
    params: dict[str, Any] = {}
    for key in ("comfyui_url", "comfyui_workflow"):
        value = fields.get(key, "").strip()
        if value:
            params[key] = value
    for key in (
        "comfyui_image_paths",
        "comfyui_prompt_paths",
        "comfyui_seed_paths",
    ):
        values = _split_comma_field(fields.get(key, ""))
        if values:
            params[key] = values
    if fields.get("comfyui_allow_no_source_patch", "").strip() in {"1", "on", "true"}:
        params["comfyui_allow_no_source_patch"] = True
    return params


def _json_object_form_field(raw: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise _FormError(HTTPStatus.BAD_REQUEST, "Media params JSON must be an object.") from exc
    if not isinstance(payload, dict):
        raise _FormError(HTTPStatus.BAD_REQUEST, "Media params JSON must be an object.")
    return payload


def _split_comma_field(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _comma_join_param(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(part) for part in value)
    if isinstance(value, str):
        return value
    return ""


def _checked(enabled: bool) -> str:
    return " checked" if enabled else ""


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


def _query_path(query: dict[str, list[str]], field_name: str) -> Path | None:
    values = query.get(field_name) or []
    raw_value = values[0].strip() if values else ""
    if not raw_value:
        return None
    return Path(raw_value).expanduser()



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


def _has_bundle_download(artifact_links: list[Any]) -> bool:
    for link in artifact_links:
        category = str(getattr(link, "category", "artifact"))
        download_name = str(getattr(link, "download_name", ""))
        media_type = str(getattr(link, "media_type", ""))
        if (
            category == "bundle"
            and download_name.lower().endswith(".3mf")
            and media_type == "model/3mf"
        ):
            return True
    return False


def _positive_count(value: Any) -> bool:
    if isinstance(value, bool):
        return bool(value)
    if isinstance(value, int | float):
        return value > 0
    try:
        return int(str(value)) > 0
    except ValueError:
        return False


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


def _as_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


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
    .beta-action-grid,
    .run-list,
    .physical-action-grid,
    .physical-family-grid,
    .readiness-grid {
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
    .run-print-verdict {
      background: #f8fafc;
      border: 1px solid #cbd5e1;
      border-radius: 8px;
      display: grid;
      gap: 4px;
      margin: 10px 0;
      padding: 10px;
    }
    .run-print-verdict span {
      color: #52606d;
      font-size: 0.78rem;
      font-weight: 750;
      text-transform: uppercase;
    }
    .run-print-verdict strong {
      color: #102a43;
    }
    .run-print-verdict p {
      margin: 0;
    }
    .run-print-verdict-review {
      background: #fff7ed;
      border-color: #fdba74;
    }
    .run-print-verdict-blocked {
      background: #fff1f2;
      border-color: #fda4af;
    }
    .run-print-verdict-ready {
      background: #ecfdf5;
      border-color: #86efac;
    }
    .final-readiness-panel {
      display: grid;
      gap: 16px;
    }
    .final-readiness-panel h3 {
      font-size: 1rem;
      margin: 0 0 8px;
    }
    .final-readiness-boundary {
      color: #334e68;
      font-weight: 600;
      margin: 8px 0 0;
    }
    .final-readiness-pillars {
      display: grid;
      gap: 12px;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    }
    .final-readiness-pillar {
      border: 1px solid #d9e2ec;
      border-radius: 8px;
      padding: 12px;
    }
    .final-readiness-pillar span {
      color: #52606d;
      display: block;
      font-size: 0.78rem;
      font-weight: 800;
      letter-spacing: 0.04em;
      margin-bottom: 4px;
    }
    .final-readiness-pillar strong {
      display: block;
      font-size: 1rem;
      margin-bottom: 6px;
      text-transform: capitalize;
    }
    .final-readiness-checklist {
      display: grid;
      gap: 10px;
      margin: 0;
      padding-left: 1.2rem;
    }
    .final-readiness-action {
      border-left: 3px solid #d9e2ec;
      padding-left: 10px;
    }
    .final-readiness-action-action-required,
    .final-readiness-action-missing,
    .final-readiness-action-insufficient-feedback {
      border-left-color: #c75233;
    }
    .final-readiness-action-passed,
    .final-readiness-action-ready {
      border-left-color: #2f855a;
    }
    .final-readiness-action pre {
      margin: 6px 0 0;
      overflow-wrap: anywhere;
      white-space: pre-wrap;
    }
    .final-readiness-links a {
      font-weight: 700;
    }
    .beta-plan-panel,
    .physical-gate-panel,
    .physical-plan-panel {
      display: grid;
      gap: 14px;
    }
    .beta-plan-panel > code,
    .physical-gate-panel code,
    .physical-plan-panel > code {
      background: #f1f5f9;
      border: 1px solid #d9e2ec;
      border-radius: 6px;
      display: inline-block;
      font-size: 0.9rem;
      overflow-wrap: anywhere;
      padding: 8px 10px;
    }
    .beta-action,
    .physical-action {
      border: 1px solid #d9e2ec;
      border-radius: 8px;
      padding: 12px;
    }
    .beta-action span,
    .physical-action span {
      color: #52606d;
      display: block;
      font-size: 0.78rem;
      font-weight: 800;
      letter-spacing: 0.04em;
      margin-bottom: 4px;
    }
    .beta-action pre,
    .physical-action pre {
      background: #102a43;
      border-radius: 6px;
      color: #f0f4f8;
      font-size: 0.78rem;
      margin: 10px 0 0;
      overflow-x: auto;
      padding: 10px;
      white-space: pre-wrap;
      word-break: break-word;
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
    .readiness-panel {
      display: grid;
      gap: 14px;
    }
    .readiness-gate {
      border: 1px solid #d9e2ec;
      border-radius: 8px;
      padding: 12px;
    }
    .readiness-gate span {
      color: #334e68;
      display: block;
      font-size: 0.84rem;
      font-weight: 800;
      margin-bottom: 4px;
    }
    .readiness-gate strong {
      display: block;
      overflow-wrap: anywhere;
    }
    .readiness-gate p {
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
