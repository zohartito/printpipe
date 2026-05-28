"""Dependency-light input processing helpers.

This module keeps media preparation honest and local: still images are copied
through stable frame folders, GIF/video extraction uses ffmpeg only when it is
available, and cleanup stages are explicit no-op copies until real background
or lighting processing exists.
"""

from __future__ import annotations

import base64
import json
import math
import os
import shlex
import shutil
import subprocess
import urllib.error
import urllib.request
from html import escape
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from printpipe.contracts import Artifact, ArtifactKind, InputKind, StageReceipt, StageStatus


IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"})
GIF_SUFFIXES = frozenset({".gif"})
VIDEO_SUFFIXES = frozenset({".mov", ".mp4", ".m4v", ".avi", ".webm"})
MESH_SUFFIXES = frozenset({".stl", ".glb", ".gltf", ".obj", ".3mf"})
DEFAULT_MAX_EXTRACTED_FRAMES = 8
BACKGROUND_REMOVAL_COMMAND_ENV = "PRINTPIPE_BACKGROUND_REMOVAL_COMMAND"
LIGHTING_NORMALIZATION_COMMAND_ENV = "PRINTPIPE_LIGHTING_NORMALIZATION_COMMAND"
PROMPT_IMAGE_COMMAND_ENV = "PRINTPIPE_PROMPT_IMAGE_COMMAND"
PROMPT_IMAGE_PROVIDER_ENV = "PRINTPIPE_PROMPT_IMAGE_PROVIDER"
OPENAI_API_KEY_ENV = "OPENAI_API_KEY"
OPENAI_IMAGE_BASE_URL_ENV = "PRINTPIPE_OPENAI_IMAGE_BASE_URL"
OPENAI_IMAGE_MODEL_ENV = "PRINTPIPE_OPENAI_IMAGE_MODEL"
OPENAI_IMAGE_SIZE_ENV = "PRINTPIPE_OPENAI_IMAGE_SIZE"
OPENAI_IMAGE_QUALITY_ENV = "PRINTPIPE_OPENAI_IMAGE_QUALITY"
OPENAI_IMAGE_BACKGROUND_ENV = "PRINTPIPE_OPENAI_IMAGE_BACKGROUND"
OPENAI_IMAGE_OUTPUT_FORMAT_ENV = "PRINTPIPE_OPENAI_IMAGE_OUTPUT_FORMAT"
OPENAI_IMAGE_ESTIMATED_COST_USD_ENV = "PRINTPIPE_OPENAI_IMAGE_ESTIMATED_COST_USD"
OPENAI_IMAGE_ESTIMATED_SECONDS_ENV = "PRINTPIPE_OPENAI_IMAGE_ESTIMATED_SECONDS"
PROMPT_IMAGE_MAX_COST_USD_ENV = "PRINTPIPE_PROMPT_IMAGE_MAX_COST_USD"
DEFAULT_OPENAI_IMAGE_MODEL = "gpt-image-2"
DEFAULT_OPENAI_IMAGE_SIZE = "1024x1024"
DEFAULT_OPENAI_IMAGE_QUALITY = "low"
DEFAULT_OPENAI_IMAGE_BACKGROUND = "auto"
DEFAULT_OPENAI_IMAGE_OUTPUT_FORMAT = "png"
DEFAULT_OPENAI_IMAGE_ESTIMATED_SECONDS = 45.0


class FrameExtractor(Protocol):
    def extract_frames(self, input_path: Path, output_dir: Path, max_frames: int) -> Sequence[Path]:
        """Extract frame files into output_dir and return their paths."""


class FrameExtractorUnavailable(RuntimeError):
    """Raised when a configured frame extractor cannot run in this environment."""


class FrameExtractionError(RuntimeError):
    """Raised when a configured frame extractor runs but does not produce usable frames."""


@dataclass(frozen=True)
class FfmpegFrameExtractor:
    executable: str = "ffmpeg"
    name: str = "ffmpeg"

    def extract_frames(self, input_path: Path, output_dir: Path, max_frames: int) -> Sequence[Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_pattern = output_dir / "frame_%06d.png"
        command = [
            self.executable,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(input_path),
            "-vf",
            "fps=1",
            "-frames:v",
            str(max_frames),
            str(output_pattern),
        ]
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
        except FileNotFoundError as exc:
            raise FrameExtractorUnavailable("ffmpeg executable was not found") from exc
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or "").strip()
            message = "ffmpeg failed to extract frames"
            if detail:
                message = f"{message}: {detail}"
            raise FrameExtractionError(message) from exc

        frame_paths = tuple(sorted(output_dir.glob("frame_*.png")))[:max_frames]
        if not frame_paths:
            raise FrameExtractionError("ffmpeg did not produce any frame files")
        return frame_paths


@dataclass(frozen=True)
class InputProcessingResult:
    kind: InputKind
    source_artifact: Artifact
    selected_references: tuple[Artifact, ...]
    receipts: tuple[StageReceipt, ...]
    mesh_artifact: Artifact | None = None
    contact_sheet: Artifact | None = None

    @property
    def needs_mesh_generation(self) -> bool:
        return self.kind != InputKind.MESH and bool(self.selected_references)


def classify_input_path(path: Path) -> InputKind:
    suffix = path.suffix.lower()
    if suffix in IMAGE_SUFFIXES:
        return InputKind.IMAGE
    if suffix in GIF_SUFFIXES:
        return InputKind.GIF
    if suffix in VIDEO_SUFFIXES:
        return InputKind.VIDEO
    if suffix in MESH_SUFFIXES:
        return InputKind.MESH
    if path.name == "prompt.txt":
        return InputKind.PROMPT
    raise ValueError(f"unsupported input type: {path.suffix or path.name}")


def prepare_input(
    input_path: Path,
    work_dir: Path,
    max_references: int = 4,
    *,
    frame_extractor: FrameExtractor | None = None,
    prompt_image_provider: str | None = None,
    use_system_ffmpeg: bool = True,
    max_extracted_frames: int = DEFAULT_MAX_EXTRACTED_FRAMES,
) -> InputProcessingResult:
    input_path = input_path.expanduser().resolve()
    if not input_path.exists():
        raise FileNotFoundError(input_path)

    work_dir = work_dir.expanduser().resolve()
    work_dir.mkdir(parents=True, exist_ok=True)

    input_kind = classify_input_path(input_path)
    source_artifact = Artifact(
        kind=ArtifactKind.ORIGINAL_INPUT,
        path=input_path,
        label="source_input",
        metadata={"input_kind": input_kind.value},
    )
    receipts: list[StageReceipt] = [
        StageReceipt(
            stage="classify_input",
            status=StageStatus.SUCCEEDED,
            message=f"classified input as {input_kind.value}",
            artifacts=(source_artifact,),
        )
    ]

    if input_kind == InputKind.MESH:
        mesh_artifact = route_existing_mesh(input_path)
        receipts.append(
            StageReceipt(
                stage="route_existing_mesh",
                status=StageStatus.SUCCEEDED,
                message="existing mesh will bypass image-to-mesh reference extraction",
                artifacts=(mesh_artifact,),
            )
        )
        receipts.append(_skipped_receipt("extract_references", "existing mesh input has no media frames to extract"))
        receipts.append(_skipped_receipt("select_references", "existing mesh input uses the mesh artifact directly"))
        return InputProcessingResult(
            kind=input_kind,
            source_artifact=source_artifact,
            selected_references=(),
            receipts=tuple(receipts),
            mesh_artifact=mesh_artifact,
        )

    extracted_references, extract_receipt = extract_references(
        input_path,
        work_dir,
        input_kind,
        frame_extractor=frame_extractor,
        prompt_image_provider=prompt_image_provider,
        use_system_ffmpeg=use_system_ffmpeg,
        max_frames=max_extracted_frames,
    )
    receipts.append(extract_receipt)

    cleaned_references, background_receipt, lighting_receipt = clean_references(extracted_references, work_dir)
    receipts.append(background_receipt)
    receipts.append(lighting_receipt)

    selected_references = select_references(
        cleaned_references,
        max_references=max_references,
        selected_dir=work_dir / "selected",
    )
    receipts.append(
        _selection_receipt(
            selected_references,
            candidate_count=len(cleaned_references),
            max_references=max_references,
        )
    )

    contact_sheet, contact_sheet_html = create_contact_sheet_artifacts(
        input_path,
        input_kind,
        selected_references,
        work_dir,
    )
    receipts.append(
        StageReceipt(
            stage="contact_sheet",
            status=StageStatus.SUCCEEDED,
            message="wrote contact-sheet manifest and HTML preview",
            artifacts=(contact_sheet, contact_sheet_html),
            metrics={"reference_count": len(selected_references)},
        )
    )

    return InputProcessingResult(
        kind=input_kind,
        source_artifact=source_artifact,
        selected_references=selected_references,
        receipts=tuple(receipts),
        contact_sheet=contact_sheet,
    )


def extract_references(
    input_path: Path,
    work_dir: Path,
    input_kind: InputKind | None = None,
    *,
    frame_extractor: FrameExtractor | None = None,
    prompt_image_provider: str | None = None,
    use_system_ffmpeg: bool = True,
    max_frames: int = DEFAULT_MAX_EXTRACTED_FRAMES,
) -> tuple[tuple[Artifact, ...], StageReceipt]:
    input_kind = input_kind or classify_input_path(input_path)

    if input_kind == InputKind.IMAGE:
        extracted_dir = work_dir / "extracted"
        reference_path = _copy_to_dir(input_path, extracted_dir)
        reference = Artifact(
            kind=ArtifactKind.CLEANED_FRAME,
            path=reference_path,
            label="extracted_frame_000",
            metadata={
                "input_kind": input_kind.value,
                "source_path": str(input_path),
                "frame_index": 0,
                "processing_stage": "extracted_frame",
                "extraction_method": "still_image_copy",
            },
        )
        return (
            (reference,),
            StageReceipt(
                stage="extract_references",
                status=StageStatus.SUCCEEDED,
                message="copied still image into extracted frame storage",
                artifacts=(reference,),
                metrics={
                    "candidate_count": 1,
                    "extraction_method": "still_image_copy",
                    "output_dir": str(extracted_dir),
                },
            ),
        )

    if input_kind == InputKind.PROMPT:
        return _generate_prompt_reference(
            input_path,
            work_dir,
            prompt_image_provider=prompt_image_provider,
        )

    if input_kind in {InputKind.GIF, InputKind.VIDEO}:
        extractor = _resolve_frame_extractor(frame_extractor, use_system_ffmpeg=use_system_ffmpeg)
        if extractor is None:
            return (
                (),
                StageReceipt(
                    stage="extract_references",
                    status=StageStatus.SKIPPED,
                    message="ffmpeg is unavailable, so GIF/video frame extraction was skipped",
                    metrics={
                        "candidate_count": 0,
                        "ffmpeg_available": False,
                        "max_frames": max_frames,
                    },
                ),
            )

        extracted_dir = work_dir / "extracted"
        extractor_name = _extractor_name(extractor)
        try:
            frame_paths = tuple(extractor.extract_frames(input_path, extracted_dir, max_frames))
        except FrameExtractorUnavailable as exc:
            return (
                (),
                StageReceipt(
                    stage="extract_references",
                    status=StageStatus.SKIPPED,
                    message=str(exc),
                    metrics={
                        "candidate_count": 0,
                        "extractor": extractor_name,
                        "ffmpeg_available": False,
                        "max_frames": max_frames,
                    },
                ),
            )
        except FrameExtractionError as exc:
            return (
                (),
                StageReceipt(
                    stage="extract_references",
                    status=StageStatus.FAILED,
                    message=str(exc),
                    metrics={
                        "candidate_count": 0,
                        "extractor": extractor_name,
                        "max_frames": max_frames,
                    },
                ),
            )

        references = tuple(
            Artifact(
                kind=ArtifactKind.CLEANED_FRAME,
                path=frame_path,
                label=f"extracted_frame_{index:03d}",
                metadata={
                    "input_kind": input_kind.value,
                    "source_path": str(input_path),
                    "frame_index": index,
                    "processing_stage": "extracted_frame",
                    "extraction_method": extractor_name,
                },
            )
            for index, frame_path in enumerate(sorted(frame_paths))
        )
        return (
            references,
            StageReceipt(
                stage="extract_references",
                status=StageStatus.SUCCEEDED,
                message="extracted media frames for reference selection",
                artifacts=references,
                metrics={
                    "candidate_count": len(references),
                    "extractor": extractor_name,
                    "max_frames": max_frames,
                    "output_dir": str(extracted_dir),
                },
            ),
        )

    return (
        (),
        StageReceipt(
            stage="extract_references",
            status=StageStatus.SKIPPED,
            message="existing mesh input has no media references to extract",
            metrics={"candidate_count": 0},
        ),
    )


def _generate_prompt_reference(
    prompt_path: Path,
    work_dir: Path,
    *,
    prompt_image_provider: str | None = None,
) -> tuple[tuple[Artifact, ...], StageReceipt]:
    try:
        provider = _resolve_prompt_image_provider(prompt_image_provider)
    except FrameExtractionError as exc:
        return (
            (),
            StageReceipt(
                stage="prompt_reference_generation",
                status=StageStatus.FAILED,
                message=str(exc),
                metrics={
                    "provider": str(prompt_image_provider or os.environ.get(PROMPT_IMAGE_PROVIDER_ENV) or "auto"),
                    "provider_configured": False,
                    "candidate_count": 0,
                },
            ),
        )
    if provider is None:
        return (
            (),
            StageReceipt(
                stage="prompt_reference_generation",
                status=StageStatus.FAILED,
                message=(
                    "prompt image provider is not configured; "
                    f"set {PROMPT_IMAGE_COMMAND_ENV} or set "
                    f"{PROMPT_IMAGE_PROVIDER_ENV}=openai with {OPENAI_API_KEY_ENV}"
                ),
                metrics={"provider": "none", "provider_configured": False, "candidate_count": 0},
            ),
        )

    provider_quote: dict[str, Any]
    try:
        provider_quote = _prompt_image_provider_quote(provider)
        _check_prompt_image_budget(provider, provider_quote)
    except FrameExtractionError as exc:
        return (
            (),
            StageReceipt(
                stage="prompt_reference_generation",
                status=StageStatus.FAILED,
                message=str(exc),
                metrics={
                    "provider": provider,
                    "provider_configured": False,
                    "candidate_count": 0,
                    "provider_quote": provider_quote if "provider_quote" in locals() else None,
                },
            ),
        )

    prompt = prompt_path.read_text(encoding="utf-8").strip()
    output_dir = work_dir / "prompt_reference"
    output_path = output_dir / "prompt_reference.png"
    try:
        metadata, receipt_metrics = _run_prompt_image_provider(
            provider,
            prompt_path=prompt_path,
            prompt=prompt,
            output_path=output_path,
        )
    except FrameExtractionError as exc:
        return (
            (),
            StageReceipt(
                stage="prompt_reference_generation",
                status=StageStatus.FAILED,
                message=str(exc),
                metrics={
                    "provider": provider,
                    "provider_configured": False,
                    "candidate_count": 0,
                    "provider_quote": provider_quote,
                },
            ),
        )

    reference = Artifact(
        kind=ArtifactKind.CLEANED_FRAME,
        path=output_path,
        label="prompt_reference_000",
        metadata={
            "input_kind": InputKind.PROMPT.value,
            "source_path": str(prompt_path),
            "frame_index": 0,
            "processing_stage": "prompt_reference",
            "prompt": prompt,
            **metadata,
        },
    )
    return (
        (reference,),
        StageReceipt(
            stage="prompt_reference_generation",
            status=StageStatus.SUCCEEDED,
            message=f"generated prompt-only reference image with {provider} provider",
            artifacts=(reference,),
            metrics={
                "provider": provider,
                "provider_configured": True,
                "candidate_count": 1,
                "output_dir": str(output_dir),
                "provider_quote": provider_quote,
                **receipt_metrics,
            },
        ),
    )


def _resolve_prompt_image_provider(requested_provider: str | None) -> str | None:
    requested = (requested_provider or os.environ.get(PROMPT_IMAGE_PROVIDER_ENV) or "auto").strip().lower()
    if requested in {"", "auto"}:
        if os.environ.get(PROMPT_IMAGE_COMMAND_ENV):
            return "command"
        if os.environ.get(OPENAI_API_KEY_ENV):
            return "openai"
        return None
    if requested in {"command", "openai"}:
        return requested
    raise FrameExtractionError(
        f"unsupported prompt image provider: {requested}; expected auto, command, or openai"
    )


def _run_prompt_image_provider(
    provider: str,
    *,
    prompt_path: Path,
    prompt: str,
    output_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if provider == "command":
        command_template = os.environ.get(PROMPT_IMAGE_COMMAND_ENV)
        if not command_template:
            raise FrameExtractionError(
                f"prompt image command provider requires {PROMPT_IMAGE_COMMAND_ENV}"
            )
        _run_prompt_image_command(
            command_template,
            prompt_path=prompt_path,
            prompt=prompt,
            output_path=output_path,
        )
        return (
            {
                "extraction_method": "configured_prompt_image_command",
                "prompt_image_provider": "command",
            },
            {"command_configured": True},
        )
    if provider == "openai":
        return _run_openai_prompt_image_provider(prompt=prompt, output_path=output_path)
    raise FrameExtractionError(
        f"unsupported prompt image provider: {provider}; expected auto, command, or openai"
    )


def _prompt_image_provider_quote(provider: str) -> dict[str, Any]:
    max_cost_usd = _optional_env_float(PROMPT_IMAGE_MAX_COST_USD_ENV)
    if provider == "command":
        return {
            "provider": "command",
            "privacy_mode": "local_or_user_configured",
            "estimated_seconds": None,
            "estimated_cost_usd": 0.0,
            "cost_estimate_configured": True,
            "max_cost_usd": max_cost_usd,
            "remote_upload": "unknown",
            "stores_prompt_with_provider": "unknown",
        }
    if provider == "openai":
        estimated_cost = _optional_env_float(OPENAI_IMAGE_ESTIMATED_COST_USD_ENV)
        estimated_seconds = _env_float(
            OPENAI_IMAGE_ESTIMATED_SECONDS_ENV,
            default=DEFAULT_OPENAI_IMAGE_ESTIMATED_SECONDS,
        )
        return {
            "provider": "openai",
            "privacy_mode": "remote_api",
            "estimated_seconds": estimated_seconds,
            "estimated_cost_usd": estimated_cost,
            "cost_estimate_configured": estimated_cost is not None,
            "max_cost_usd": max_cost_usd,
            "remote_upload": True,
            "stores_prompt_with_provider": True,
        }
    raise FrameExtractionError(
        f"unsupported prompt image provider: {provider}; expected auto, command, or openai"
    )


def _check_prompt_image_budget(provider: str, provider_quote: dict[str, Any]) -> None:
    if provider != "openai":
        return
    max_cost = provider_quote.get("max_cost_usd")
    if max_cost is None:
        return
    estimated_cost = provider_quote.get("estimated_cost_usd")
    if estimated_cost is None:
        raise FrameExtractionError(
            "OpenAI prompt image cost cap cannot be checked because "
            f"{OPENAI_IMAGE_ESTIMATED_COST_USD_ENV} is not set"
        )
    if float(estimated_cost) > float(max_cost):
        raise FrameExtractionError(
            f"OpenAI prompt image estimated cost {estimated_cost:g} USD exceeds cap "
            f"{float(max_cost):g} USD"
        )


def _optional_env_float(name: str) -> float | None:
    value = os.environ.get(name)
    if value in {None, ""}:
        return None
    return _parse_env_float(name, value)


def _env_float(name: str, *, default: float) -> float:
    value = os.environ.get(name)
    if value in {None, ""}:
        return default
    return _parse_env_float(name, value)


def _parse_env_float(name: str, value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise FrameExtractionError(f"{name} must be a numeric value") from exc
    if not math.isfinite(parsed) or parsed < 0:
        raise FrameExtractionError(f"{name} must be a non-negative finite number")
    return parsed


def _run_openai_prompt_image_provider(
    *,
    prompt: str,
    output_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    api_key = os.environ.get(OPENAI_API_KEY_ENV)
    if not api_key:
        raise FrameExtractionError(f"OpenAI prompt image provider requires {OPENAI_API_KEY_ENV}")

    model = os.environ.get(OPENAI_IMAGE_MODEL_ENV, DEFAULT_OPENAI_IMAGE_MODEL)
    size = os.environ.get(OPENAI_IMAGE_SIZE_ENV, DEFAULT_OPENAI_IMAGE_SIZE)
    quality = os.environ.get(OPENAI_IMAGE_QUALITY_ENV, DEFAULT_OPENAI_IMAGE_QUALITY)
    background = os.environ.get(OPENAI_IMAGE_BACKGROUND_ENV, DEFAULT_OPENAI_IMAGE_BACKGROUND)
    output_format = os.environ.get(OPENAI_IMAGE_OUTPUT_FORMAT_ENV, DEFAULT_OPENAI_IMAGE_OUTPUT_FORMAT)
    base_url = os.environ.get(OPENAI_IMAGE_BASE_URL_ENV, "https://api.openai.com/v1").rstrip("/")
    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "n": 1,
        "size": size,
        "quality": quality,
        "background": background,
        "output_format": output_format,
    }
    request = urllib.request.Request(
        f"{base_url}/images/generations",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace").strip()
        message = f"OpenAI prompt image request failed with HTTP {exc.code}"
        if detail:
            message = f"{message}: {detail}"
        raise FrameExtractionError(message) from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise FrameExtractionError(f"OpenAI prompt image request failed: {exc}") from exc

    image_b64 = _openai_image_b64(response_payload)
    try:
        image_bytes = base64.b64decode(image_b64, validate=True)
    except ValueError as exc:
        raise FrameExtractionError("OpenAI prompt image response contained invalid base64") from exc
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(image_bytes)
    usage = response_payload.get("usage")
    receipt_metrics: dict[str, Any] = {
        "model": model,
        "size": size,
        "quality": quality,
        "background": background,
        "output_format": output_format,
    }
    if isinstance(usage, dict):
        receipt_metrics["usage"] = usage
    return (
        {
            "extraction_method": "openai_image_generation",
            "prompt_image_provider": "openai",
            "model": model,
        },
        receipt_metrics,
    )


def _openai_image_b64(payload: Any) -> str:
    if not isinstance(payload, dict):
        raise FrameExtractionError("OpenAI prompt image response was not a JSON object")
    data = payload.get("data")
    if not isinstance(data, list) or not data:
        raise FrameExtractionError("OpenAI prompt image response did not include data")
    first = data[0]
    if not isinstance(first, dict):
        raise FrameExtractionError("OpenAI prompt image response data item was invalid")
    image_b64 = first.get("b64_json")
    if not isinstance(image_b64, str) or not image_b64:
        raise FrameExtractionError("OpenAI prompt image response did not include data[0].b64_json")
    return image_b64


def clean_references(
    references: tuple[Artifact, ...],
    work_dir: Path,
) -> tuple[tuple[Artifact, ...], StageReceipt, StageReceipt]:
    if not references:
        return (
            (),
            _skipped_receipt(
                "background_removal",
                "no extracted frames were available for background removal",
                metrics={"frame_count": 0, "semantic_background_removed": False},
            ),
            _skipped_receipt(
                "normalize_lighting",
                "no cleaned frames were available for lighting normalization",
                metrics={"frame_count": 0, "lighting_normalized": False},
            ),
        )

    background_command = os.environ.get(BACKGROUND_REMOVAL_COMMAND_ENV)
    lighting_command = os.environ.get(LIGHTING_NORMALIZATION_COMMAND_ENV)
    background_references, background_receipt = _background_removed_references(
        references,
        work_dir,
        command_template=background_command,
    )
    cleaned_references, lighting_receipt = _lighting_normalized_references(
        background_references,
        work_dir,
        command_template=lighting_command,
        already_cleaned=background_command is None,
    )
    return cleaned_references, background_receipt, lighting_receipt


def _background_removed_references(
    references: tuple[Artifact, ...],
    work_dir: Path,
    *,
    command_template: str | None,
) -> tuple[tuple[Artifact, ...], StageReceipt]:
    if command_template:
        processed = _run_frame_command_stage(
            references,
            output_dir=work_dir / "background_removed",
            command_template=command_template,
            label_prefix="background_removed_frame",
            metadata_updates={
                "semantic_background_removed": True,
                "background_removal_method": "configured_command",
            },
        )
        return (
            processed,
            StageReceipt(
                stage="background_removal",
                status=StageStatus.SUCCEEDED,
                message="removed backgrounds with configured frame command",
                artifacts=processed,
                metrics={
                    "frame_count": len(processed),
                    "operation": "configured_command",
                    "command_configured": True,
                    "semantic_background_removed": True,
                },
            ),
        )

    cleaned = _copy_references_with_metadata(
        references,
        output_dir=work_dir / "cleaned",
        label_prefix="cleaned_frame",
        metadata_updates={
            "semantic_background_removed": False,
            "background_removal_method": "not_performed_copy",
            "lighting_normalized": False,
            "lighting_normalization_method": "not_performed",
        },
    )
    return (
        cleaned,
        StageReceipt(
            stage="background_removal",
            status=StageStatus.SKIPPED,
            message="copied frames without semantic background removal",
            artifacts=cleaned,
            metrics={
                "frame_count": len(cleaned),
                "operation": "copy",
                "command_configured": False,
                "semantic_background_removed": False,
            },
        ),
    )


def _lighting_normalized_references(
    references: tuple[Artifact, ...],
    work_dir: Path,
    *,
    command_template: str | None,
    already_cleaned: bool,
) -> tuple[tuple[Artifact, ...], StageReceipt]:
    if command_template:
        processed = _run_frame_command_stage(
            references,
            output_dir=work_dir / "cleaned",
            command_template=command_template,
            label_prefix="cleaned_frame",
            metadata_updates={
                "lighting_normalized": True,
                "lighting_normalization_method": "configured_command",
            },
        )
        return (
            processed,
            StageReceipt(
                stage="normalize_lighting",
                status=StageStatus.SUCCEEDED,
                message="normalized lighting with configured frame command",
                artifacts=processed,
                metrics={
                    "frame_count": len(processed),
                    "operation": "configured_command",
                    "command_configured": True,
                    "lighting_normalized": True,
                },
            ),
        )

    cleaned = references if already_cleaned else _copy_references_with_metadata(
        references,
        output_dir=work_dir / "cleaned",
        label_prefix="cleaned_frame",
        metadata_updates={
            "lighting_normalized": False,
            "lighting_normalization_method": "not_performed",
        },
    )
    return (
        cleaned,
        StageReceipt(
            stage="normalize_lighting",
            status=StageStatus.SKIPPED,
            message="left cleaned frames unchanged; no lighting normalization was applied",
            artifacts=cleaned,
            metrics={
                "frame_count": len(cleaned),
                "operation": "no_op",
                "command_configured": False,
                "lighting_normalized": False,
            },
        ),
    )


def _run_frame_command_stage(
    references: tuple[Artifact, ...],
    *,
    output_dir: Path,
    command_template: str,
    label_prefix: str,
    metadata_updates: dict[str, object],
) -> tuple[Artifact, ...]:
    processed: list[Artifact] = []
    for index, reference in enumerate(references):
        output_path = output_dir / reference.path.name
        _run_configured_frame_command(command_template, reference.path, output_path)
        metadata = _cleanup_metadata(reference, metadata_updates)
        processed.append(
            Artifact(
                kind=ArtifactKind.CLEANED_FRAME,
                path=output_path,
                label=f"{label_prefix}_{index:03d}",
                metadata=metadata,
            )
        )
    return tuple(processed)


def _copy_references_with_metadata(
    references: tuple[Artifact, ...],
    *,
    output_dir: Path,
    label_prefix: str,
    metadata_updates: dict[str, object],
) -> tuple[Artifact, ...]:
    copied: list[Artifact] = []
    for index, reference in enumerate(references):
        output_path = _copy_to_dir(reference.path, output_dir)
        metadata = _cleanup_metadata(reference, metadata_updates)
        copied.append(
            Artifact(
                kind=ArtifactKind.CLEANED_FRAME,
                path=output_path,
                label=f"{label_prefix}_{index:03d}",
                metadata=metadata,
            )
        )
    return tuple(copied)


def _cleanup_metadata(reference: Artifact, updates: dict[str, object]) -> dict[str, object]:
    metadata: dict[str, object] = dict(reference.metadata)
    metadata.update(
        {
            "processing_stage": "cleaned_frame",
            "source_frame_path": str(reference.path),
        }
    )
    metadata.update(updates)
    return metadata


def _run_configured_frame_command(
    command_template: str,
    input_path: Path,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = _frame_command_args(command_template, input_path=input_path, output_path=output_path)
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        message = "configured frame command failed"
        if detail:
            message = f"{message}: {detail}"
        raise FrameExtractionError(message) from exc
    if not output_path.exists():
        raise FrameExtractionError(f"configured frame command did not write {output_path}")


def _run_prompt_image_command(
    command_template: str,
    *,
    prompt_path: Path,
    prompt: str,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = _prompt_image_command_args(
        command_template,
        prompt_path=prompt_path,
        prompt=prompt,
        output_path=output_path,
    )
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        message = "configured prompt image command failed"
        if detail:
            message = f"{message}: {detail}"
        raise FrameExtractionError(message) from exc
    if not output_path.exists():
        raise FrameExtractionError(
            f"configured prompt image command did not write {output_path}"
        )


def _frame_command_args(command_template: str, *, input_path: Path, output_path: Path) -> list[str]:
    tokens = shlex.split(command_template)
    if "{input}" not in tokens or "{output}" not in tokens:
        raise FrameExtractionError("configured frame command must include {input} and {output}")
    return [
        str(input_path) if token == "{input}" else str(output_path) if token == "{output}" else token
        for token in tokens
    ]


def _prompt_image_command_args(
    command_template: str,
    *,
    prompt_path: Path,
    prompt: str,
    output_path: Path,
) -> list[str]:
    tokens = shlex.split(command_template)
    if "{prompt_file}" not in tokens or "{output}" not in tokens:
        raise FrameExtractionError(
            "configured prompt image command must include {prompt_file} and {output}"
        )
    return [
        str(prompt_path)
        if token == "{prompt_file}"
        else str(output_path)
        if token == "{output}"
        else prompt
        if token == "{prompt}"
        else token
        for token in tokens
    ]


def select_references(
    references: tuple[Artifact, ...],
    max_references: int = 4,
    selected_dir: Path | None = None,
) -> tuple[Artifact, ...]:
    if max_references < 1:
        raise ValueError("max_references must be at least 1")
    ranked = _rank_reference_candidates(references, max_references=max_references)
    if selected_dir is None:
        return tuple(reference for _, reference in ranked)

    selected_references: list[Artifact] = []
    for index, (source_index, reference) in enumerate(ranked):
        selected_path = _copy_to_dir(reference.path, selected_dir)
        metadata = dict(reference.metadata)
        source_frame_index = metadata.get("frame_index", source_index)
        metadata.update(
            {
                "processing_stage": "selected_reference",
                "selected_from": str(reference.path),
                "selection_rank": index,
                "selection_strategy": "representative_frame_spread",
                "selection_candidate_count": len(references),
                "source_frame_index": source_frame_index,
            }
        )
        selected_references.append(
            Artifact(
                kind=reference.kind,
                path=selected_path,
                label=f"selected_reference_{index:03d}",
                metadata=metadata,
            )
        )
    return tuple(selected_references)


def _rank_reference_candidates(
    references: tuple[Artifact, ...],
    *,
    max_references: int,
) -> tuple[tuple[int, Artifact], ...]:
    if len(references) <= max_references:
        return tuple(enumerate(references))
    return tuple((index, references[index]) for index in _spread_indices(len(references), max_references))


def _spread_indices(candidate_count: int, selected_count: int) -> tuple[int, ...]:
    if candidate_count < 1:
        return ()
    if selected_count <= 1:
        return (candidate_count // 2,)

    indices: list[int] = []
    for rank in range(selected_count):
        index = round(rank * (candidate_count - 1) / (selected_count - 1))
        if index not in indices:
            indices.append(index)

    fill_index = 0
    while len(indices) < min(candidate_count, selected_count):
        if fill_index not in indices:
            indices.append(fill_index)
        fill_index += 1
    return tuple(sorted(indices))


def route_existing_mesh(input_path: Path) -> Artifact:
    return Artifact(
        kind=ArtifactKind.ORIGINAL_INPUT,
        path=input_path,
        label="existing_mesh_input",
        metadata={
            "input_kind": InputKind.MESH.value,
            "route": "existing_mesh_import",
        },
    )


def create_contact_sheet_manifest(
    input_path: Path,
    input_kind: InputKind,
    references: tuple[Artifact, ...],
    work_dir: Path,
) -> Artifact:
    manifest, _html_artifact = create_contact_sheet_artifacts(input_path, input_kind, references, work_dir)
    return manifest


def create_contact_sheet_artifacts(
    input_path: Path,
    input_kind: InputKind,
    references: tuple[Artifact, ...],
    work_dir: Path,
) -> tuple[Artifact, Artifact]:
    work_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = work_dir / "contact_sheet_manifest.json"
    html_path = work_dir / "contact_sheet.html"
    payload = {
        "schema_version": 1,
        "placeholder": False,
        "preview_manifest": True,
        "input_kind": input_kind.value,
        "source_path": str(input_path),
        "html_path": str(html_path),
        "reference_count": len(references),
        "references": [
            {
                "label": reference.label,
                "kind": reference.kind.value,
                "path": str(reference.path),
                "relative_path": _relative_artifact_ref(reference.path, work_dir),
                "metadata": reference.metadata,
            }
            for reference in references
        ],
        "preview_items": [
            {
                "label": reference.label,
                "path": str(reference.path),
                "relative_path": _relative_artifact_ref(reference.path, work_dir),
                "source_frame_path": reference.metadata.get("selected_from"),
            }
            for reference in references
        ],
    }
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    html_path.write_text(_render_contact_sheet_html(payload), encoding="utf-8")
    manifest_artifact = Artifact(
        kind=ArtifactKind.PREVIEW,
        path=manifest_path,
        label="contact_sheet_manifest",
        metadata={
            "format": "json-manifest",
            "reference_count": len(references),
            "preview_manifest": True,
            "paired_html": str(html_path),
        },
    )
    html_artifact = Artifact(
        kind=ArtifactKind.PREVIEW,
        path=html_path,
        label="contact_sheet_html",
        metadata={
            "format": "html",
            "reference_count": len(references),
            "preview_manifest": False,
            "source_manifest": str(manifest_path),
        },
    )
    return manifest_artifact, html_artifact


def _render_contact_sheet_html(payload: dict[str, object]) -> str:
    input_kind = escape(str(payload["input_kind"]))
    source_path = escape(str(payload["source_path"]))
    reference_count = escape(str(payload["reference_count"]))
    references = payload["references"]
    if not isinstance(references, list):
        references = []

    if references:
        cards = "\n".join(_render_contact_sheet_card(reference) for reference in references)
    else:
        cards = '<p class="empty">No selected references were available for preview.</p>'

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PrintPipe Contact Sheet</title>
  <style>
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: #171717;
      background: #f6f7f8;
    }}
    main {{
      max-width: 1120px;
      margin: 0 auto;
      padding: 32px 20px;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 28px;
      letter-spacing: 0;
    }}
    .summary {{
      margin: 0 0 24px;
      color: #4a5562;
      line-height: 1.5;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 16px;
    }}
    .card {{
      overflow: hidden;
      border: 1px solid #d7dce2;
      border-radius: 8px;
      background: #fff;
    }}
    .thumb {{
      display: block;
      width: 100%;
      aspect-ratio: 4 / 3;
      object-fit: contain;
      background: #e9edf2;
    }}
    .fallback {{
      display: grid;
      min-height: 160px;
      place-items: center;
      padding: 16px;
      background: #e9edf2;
      color: #53606f;
      text-align: center;
    }}
    .details {{
      padding: 12px;
    }}
    .label {{
      margin: 0 0 8px;
      font-weight: 700;
    }}
    dl {{
      display: grid;
      grid-template-columns: max-content 1fr;
      gap: 4px 10px;
      margin: 0;
      font-size: 13px;
    }}
    dt {{
      color: #5d6876;
    }}
    dd {{
      margin: 0;
      overflow-wrap: anywhere;
    }}
    pre {{
      margin: 10px 0 0;
      padding: 8px;
      overflow: auto;
      border-radius: 6px;
      background: #f2f4f6;
      font-size: 12px;
      line-height: 1.35;
    }}
    .empty {{
      margin: 0;
      padding: 16px;
      border: 1px solid #d7dce2;
      border-radius: 8px;
      background: #fff;
    }}
  </style>
</head>
<body>
  <main>
    <h1>PrintPipe Contact Sheet</h1>
    <p class="summary">Input kind: {input_kind}. Selected references: {reference_count}. Source: {source_path}</p>
    <section class="grid" aria-label="Selected references">
{cards}
    </section>
  </main>
</body>
</html>
"""


def _render_contact_sheet_card(reference: object) -> str:
    if not isinstance(reference, dict):
        return ""

    label = escape(str(reference.get("label", "reference")))
    kind = escape(str(reference.get("kind", "")))
    path = escape(str(reference.get("path", "")))
    relative_path = str(reference.get("relative_path") or reference.get("path") or "")
    href = escape(relative_path, quote=True)
    metadata = reference.get("metadata", {})
    metadata_json = escape(json.dumps(metadata, indent=2, sort_keys=True), quote=False)

    if _is_preview_image(Path(relative_path)):
        preview = f'<a href="{href}"><img class="thumb" src="{href}" alt="{label}"></a>'
    else:
        preview = f'<a class="fallback" href="{href}">Open artifact</a>'

    return f"""      <article class="card">
        {preview}
        <div class="details">
          <p class="label">{label}</p>
          <dl>
            <dt>Kind</dt><dd>{kind}</dd>
            <dt>Path</dt><dd><a href="{href}">{path}</a></dd>
          </dl>
          <pre>{metadata_json}</pre>
        </div>
      </article>"""


def _relative_artifact_ref(path: Path, base_dir: Path) -> str:
    try:
        return path.resolve().relative_to(base_dir.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _is_preview_image(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_SUFFIXES


def _selection_receipt(
    selected_references: tuple[Artifact, ...],
    *,
    candidate_count: int | None = None,
    max_references: int | None = None,
) -> StageReceipt:
    metrics = {
        "selected_count": len(selected_references),
        "candidate_count": candidate_count if candidate_count is not None else len(selected_references),
    }
    if max_references is not None:
        metrics["max_references"] = max_references
    if selected_references:
        metrics["selection_strategy"] = _selected_strategy(selected_references)
        metrics["selected_source_frame_indices"] = [
            reference.metadata.get("source_frame_index")
            for reference in selected_references
            if "source_frame_index" in reference.metadata
        ]
    if selected_references:
        return StageReceipt(
            stage="select_references",
            status=StageStatus.SUCCEEDED,
            message="selected reference artifacts for mesh generation",
            artifacts=selected_references,
            metrics=metrics,
        )
    return StageReceipt(
        stage="select_references",
        status=StageStatus.SKIPPED,
        message="no extracted references are available yet",
        metrics=metrics,
    )


def _selected_strategy(selected_references: tuple[Artifact, ...]) -> str:
    strategies = {
        str(reference.metadata.get("selection_strategy"))
        for reference in selected_references
        if reference.metadata.get("selection_strategy")
    }
    if len(strategies) == 1:
        return next(iter(strategies))
    if strategies:
        return "mixed"
    return "unknown"


def _resolve_frame_extractor(
    frame_extractor: FrameExtractor | None,
    *,
    use_system_ffmpeg: bool,
) -> FrameExtractor | None:
    if frame_extractor is not None:
        return frame_extractor
    if not use_system_ffmpeg:
        return None
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path is None:
        return None
    return FfmpegFrameExtractor(executable=ffmpeg_path)


def _extractor_name(frame_extractor: FrameExtractor) -> str:
    return str(getattr(frame_extractor, "name", frame_extractor.__class__.__name__))


def _copy_to_dir(source_path: Path, target_dir: Path) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / source_path.name
    shutil.copy2(source_path, target_path)
    return target_path


def _skipped_receipt(stage: str, message: str, metrics: dict[str, object] | None = None) -> StageReceipt:
    return StageReceipt(stage=stage, status=StageStatus.SKIPPED, message=message, metrics=metrics or {})
