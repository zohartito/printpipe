"""Dependency-light input processing skeleton.

This module deliberately works by extension and file copying only. Heavier
media decoding, background removal, and contrast normalization can be wired in
later without changing the public receipts.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from printpipe.contracts import Artifact, ArtifactKind, InputKind, StageReceipt, StageStatus


IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"})
GIF_SUFFIXES = frozenset({".gif"})
VIDEO_SUFFIXES = frozenset({".mov", ".mp4", ".m4v", ".avi", ".webm"})
MESH_SUFFIXES = frozenset({".stl", ".glb", ".gltf", ".obj", ".3mf"})


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


def prepare_input(input_path: Path, work_dir: Path, max_references: int = 4) -> InputProcessingResult:
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

    extracted_references, extract_receipt = extract_references(input_path, work_dir, input_kind)
    receipts.append(extract_receipt)

    selected_references = select_references(extracted_references, max_references=max_references)
    receipts.append(_selection_receipt(selected_references))
    receipts.append(_skipped_receipt("background_removal", "background removal is not implemented in the v1 skeleton"))
    receipts.append(_skipped_receipt("normalize_lighting", "lighting normalization is not implemented in the v1 skeleton"))

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


def extract_references(input_path: Path, work_dir: Path, input_kind: InputKind | None = None) -> tuple[tuple[Artifact, ...], StageReceipt]:
    input_kind = input_kind or classify_input_path(input_path)

    if input_kind == InputKind.IMAGE:
        selected_dir = work_dir / "selected"
        selected_dir.mkdir(parents=True, exist_ok=True)
        reference_path = selected_dir / input_path.name
        shutil.copy2(input_path, reference_path)
        reference = Artifact(
            kind=ArtifactKind.CLEANED_FRAME,
            path=reference_path,
            label="selected_reference_000",
            metadata={
                "input_kind": input_kind.value,
                "source_path": str(input_path),
                "frame_index": 0,
                "selection_role": "still_image_reference",
            },
        )
        return (
            (reference,),
            StageReceipt(
                stage="extract_references",
                status=StageStatus.SUCCEEDED,
                message="copied still image as the initial selected reference",
                artifacts=(reference,),
                metrics={"candidate_count": 1},
            ),
        )

    if input_kind in {InputKind.GIF, InputKind.VIDEO}:
        media_type = "GIF frame extraction" if input_kind == InputKind.GIF else "video decoding"
        return (
            (),
            StageReceipt(
                stage="extract_references",
                status=StageStatus.SKIPPED,
                message=f"{media_type} is not implemented in the v1 skeleton",
                metrics={"candidate_count": 0},
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


def select_references(references: tuple[Artifact, ...], max_references: int = 4) -> tuple[Artifact, ...]:
    if max_references < 1:
        raise ValueError("max_references must be at least 1")
    return references[:max_references]


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
    }
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return Artifact(
        kind=ArtifactKind.PREVIEW,
        path=manifest_path,
        label="contact_sheet_manifest",
        metadata={
            "format": "json-placeholder",
            "reference_count": len(references),
        },
    )


def _selection_receipt(selected_references: tuple[Artifact, ...]) -> StageReceipt:
    if selected_references:
        return StageReceipt(
            stage="select_references",
            status=StageStatus.SUCCEEDED,
            message="selected reference artifacts for mesh generation",
            artifacts=selected_references,
            metrics={"selected_count": len(selected_references)},
        )
    return StageReceipt(
        stage="select_references",
        status=StageStatus.SKIPPED,
        message="no extracted references are available yet",
        metrics={"selected_count": 0},
    )


def _skipped_receipt(stage: str, message: str) -> StageReceipt:
    return StageReceipt(stage=stage, status=StageStatus.SKIPPED, message=message)
