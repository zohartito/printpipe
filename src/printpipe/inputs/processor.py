"""Dependency-light input processing helpers.

This module keeps media preparation honest and local: still images are copied
through stable frame folders, GIF/video extraction uses ffmpeg only when it is
available, and cleanup stages are explicit no-op copies until real background
or lighting processing exists.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from printpipe.contracts import Artifact, ArtifactKind, InputKind, StageReceipt, StageStatus


IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"})
GIF_SUFFIXES = frozenset({".gif"})
VIDEO_SUFFIXES = frozenset({".mov", ".mp4", ".m4v", ".avi", ".webm"})
MESH_SUFFIXES = frozenset({".stl", ".glb", ".gltf", ".obj", ".3mf"})
DEFAULT_MAX_EXTRACTED_FRAMES = 8


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
    raise ValueError(f"unsupported input type: {path.suffix or path.name}")


def prepare_input(
    input_path: Path,
    work_dir: Path,
    max_references: int = 4,
    *,
    frame_extractor: FrameExtractor | None = None,
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

    contact_sheet = create_contact_sheet_manifest(input_path, input_kind, selected_references, work_dir)
    receipts.append(
        StageReceipt(
            stage="contact_sheet",
            status=StageStatus.SUCCEEDED,
            message="wrote contact-sheet manifest placeholder",
            artifacts=(contact_sheet,),
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

    cleaned_dir = work_dir / "cleaned"
    cleaned_references: list[Artifact] = []
    for index, reference in enumerate(references):
        cleaned_path = _copy_to_dir(reference.path, cleaned_dir)
        metadata = dict(reference.metadata)
        metadata.update(
            {
                "processing_stage": "cleaned_frame",
                "source_frame_path": str(reference.path),
                "semantic_background_removed": False,
                "background_removal_method": "not_performed_copy",
                "lighting_normalized": False,
                "lighting_normalization_method": "not_performed",
            }
        )
        cleaned_references.append(
            Artifact(
                kind=ArtifactKind.CLEANED_FRAME,
                path=cleaned_path,
                label=f"cleaned_frame_{index:03d}",
                metadata=metadata,
            )
        )

    cleaned = tuple(cleaned_references)
    return (
        cleaned,
        StageReceipt(
            stage="background_removal",
            status=StageStatus.SUCCEEDED,
            message="copied frames without semantic background removal",
            artifacts=cleaned,
            metrics={
                "frame_count": len(cleaned),
                "operation": "copy",
                "semantic_background_removed": False,
            },
        ),
        StageReceipt(
            stage="normalize_lighting",
            status=StageStatus.SUCCEEDED,
            message="left cleaned frames unchanged; no lighting normalization was applied",
            artifacts=cleaned,
            metrics={
                "frame_count": len(cleaned),
                "operation": "no_op",
                "lighting_normalized": False,
            },
        ),
    )


def select_references(
    references: tuple[Artifact, ...],
    max_references: int = 4,
    selected_dir: Path | None = None,
) -> tuple[Artifact, ...]:
    if max_references < 1:
        raise ValueError("max_references must be at least 1")
    selected = references[:max_references]
    if selected_dir is None:
        return selected

    selected_references: list[Artifact] = []
    for index, reference in enumerate(selected):
        selected_path = _copy_to_dir(reference.path, selected_dir)
        metadata = dict(reference.metadata)
        metadata.update(
            {
                "processing_stage": "selected_reference",
                "selected_from": str(reference.path),
                "selection_rank": index,
                "selection_strategy": "first_available_frames",
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
    manifest_path = work_dir / "contact_sheet_manifest.json"
    payload = {
        "schema_version": 1,
        "placeholder": True,
        "preview_manifest": True,
        "input_kind": input_kind.value,
        "source_path": str(input_path),
        "reference_count": len(references),
        "references": [
            {
                "label": reference.label,
                "kind": reference.kind.value,
                "path": str(reference.path),
                "metadata": reference.metadata,
            }
            for reference in references
        ],
        "preview_items": [
            {
                "label": reference.label,
                "path": str(reference.path),
                "source_frame_path": reference.metadata.get("selected_from"),
            }
            for reference in references
        ],
    }
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return Artifact(
        kind=ArtifactKind.PREVIEW,
        path=manifest_path,
        label="contact_sheet_manifest",
        metadata={
            "format": "json-manifest",
            "reference_count": len(references),
            "preview_manifest": True,
        },
    )


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
