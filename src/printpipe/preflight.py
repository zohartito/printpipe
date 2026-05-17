"""Pre-print checklist helpers for report payloads."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PreflightContext:
    """Small context bundle for building a report-ready checklist."""

    material: str
    printer: str
    use_case: str
    slice_gate_status: bool | str | Mapping[str, Any] | None = None


def build_pre_print_checklist(
    context: PreflightContext | None = None,
    *,
    material: str | None = None,
    printer: str | None = None,
    use_case: str | None = None,
    slice_gate_status: bool | str | Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return JSON-serializable pre-print checklist items for run reports."""

    resolved = _resolve_context(
        context,
        material=material,
        printer=printer,
        use_case=use_case,
        slice_gate_status=slice_gate_status,
    )
    material_family = _material_family(resolved.material)

    return [
        _dry_filament_item(material_family, resolved),
        _feed_path_item(material_family, resolved),
        _layer_preview_item(resolved),
        _slice_gate_item(resolved.slice_gate_status),
        _first_layer_item(resolved),
        _flex_coupon_item(material_family, resolved),
    ]


def _resolve_context(
    context: PreflightContext | None,
    *,
    material: str | None,
    printer: str | None,
    use_case: str | None,
    slice_gate_status: bool | str | Mapping[str, Any] | None,
) -> PreflightContext:
    if context is not None:
        if material is not None or printer is not None or use_case is not None:
            raise ValueError("pass either context or keyword fields, not both")
        if slice_gate_status is not None:
            return PreflightContext(
                material=context.material,
                printer=context.printer,
                use_case=context.use_case,
                slice_gate_status=slice_gate_status,
            )
        return context

    return PreflightContext(
        material=(material or "Unknown material").strip() or "Unknown material",
        printer=(printer or "Unknown printer").strip() or "Unknown printer",
        use_case=(use_case or "print").strip() or "print",
        slice_gate_status=slice_gate_status,
    )


def _material_family(material: str) -> str:
    normalized = material.upper()
    if "TPU" in normalized or "TPE" in normalized or "FLEX" in normalized:
        return "flexible"
    if "PETG" in normalized:
        return "petg"
    if "PLA" in normalized:
        return "pla"
    return "generic"


def _dry_filament_item(material_family: str, context: PreflightContext) -> dict[str, Any]:
    if material_family == "flexible":
        return _item(
            "dry_filament",
            "material",
            "Dry TPU before printing",
            "Dry TPU at 50 C for 4-8 h before long prints; keep it dry during the run if possible.",
            "required",
            context,
        )
    if material_family == "petg":
        return _item(
            "dry_filament",
            "material",
            f"Dry-check {context.material}",
            "PETG is moisture-sensitive; dry it before cosmetic, structural, or long prints if there is any popping, stringing, or rough surface texture.",
            "recommended",
            context,
        )
    if material_family == "pla":
        return _item(
            "dry_filament",
            "material",
            f"Check {context.material} dryness",
            "PLA usually prints from ambient storage, but dry it if the filament is brittle, popping, stringy, or surface quality matters.",
            "optional",
            context,
        )
    return _item(
        "dry_filament",
        "material",
        f"Check {context.material} drying needs",
        "Confirm drying guidance for the selected material before starting a long print.",
        "review",
        context,
    )


def _feed_path_item(material_family: str, context: PreflightContext) -> dict[str, Any]:
    if material_family == "flexible":
        return _item(
            "feed_path",
            "hardware",
            "Use external spool path for flexible filament",
            "Feed soft TPU from an external spool holder or dryer with a short, low-drag path; do not use AMS unless this exact filament is explicitly AMS-compatible.",
            "required",
            context,
        )
    return _item(
        "feed_path",
        "hardware",
        "Confirm spool path",
        "Use the normal spool path for the selected printer and confirm AMS compatibility for the specific filament before loading it through AMS.",
        "review",
        context,
    )


def _layer_preview_item(context: PreflightContext) -> dict[str, Any]:
    return _item(
        "layer_preview",
        "slicer",
        "Review Bambu Studio layer preview",
        "Inspect the layer preview for floating islands, missing supports, off-bed geometry, overhang risk, and unexpected first-layer contact before sending the job.",
        "required",
        context,
    )


def _slice_gate_item(slice_gate_status: bool | str | Mapping[str, Any] | None) -> dict[str, Any]:
    status, detail, metadata = _normalize_slice_gate(slice_gate_status)
    return {
        "id": "slice_gate",
        "category": "slicer",
        "title": "Confirm slice gate status",
        "detail": detail,
        "status": status,
        "metadata": metadata,
    }


def _first_layer_item(context: PreflightContext) -> dict[str, Any]:
    return _item(
        "first_layer_inspection",
        "printer",
        "Inspect the first layer",
        f"Watch the first layer on {context.printer}; stop early if adhesion, brim separation, nozzle drag, or extrusion consistency looks wrong.",
        "required",
        context,
    )


def _flex_coupon_item(material_family: str, context: PreflightContext) -> dict[str, Any]:
    if material_family == "flexible":
        return _item(
            "flex_coupon_first",
            "validation",
            "Print a flex coupon first",
            f"Before the full {context.use_case}, print a 30-50 mm coupon with the same material, walls, infill, supports, and cooling to validate flex, adhesion, and support removal.",
            "required",
            context,
        )
    return _item(
        "flex_coupon_first",
        "validation",
        "Flex coupon not required",
        "This checklist item is only required for flexible materials; use a smaller calibration print instead if the part is large or high-risk.",
        "not_applicable",
        context,
    )


def _normalize_slice_gate(
    slice_gate_status: bool | str | Mapping[str, Any] | None,
) -> tuple[str, str, dict[str, Any]]:
    if slice_gate_status is None:
        return "unknown", "Slice gate has not run yet.", {}

    if isinstance(slice_gate_status, bool):
        if slice_gate_status:
            return "passed", "Slice gate passed.", {}
        return "failed", "Slice gate failed; resolve slicer errors before printing.", {}

    if isinstance(slice_gate_status, str):
        status = _normalize_status(slice_gate_status)
        return status, _slice_gate_detail_for_status(status), {}

    status = _normalize_status(str(slice_gate_status.get("status", "unknown")))
    detail = str(
        slice_gate_status.get("message")
        or slice_gate_status.get("detail")
        or _slice_gate_detail_for_status(status)
    )
    metadata = {
        key: value
        for key, value in slice_gate_status.items()
        if key not in {"status", "message", "detail"}
    }
    return status, detail, metadata


def _normalize_status(status: str) -> str:
    normalized = status.strip().lower().replace(" ", "_")
    aliases = {
        "ok": "passed",
        "pass": "passed",
        "succeeded": "passed",
        "success": "passed",
        "error": "failed",
        "fail": "failed",
        "critical": "failed",
        "warn": "warning",
        "warnings": "warning",
    }
    return aliases.get(normalized, normalized or "unknown")


def _slice_gate_detail_for_status(status: str) -> str:
    if status == "passed":
        return "Slice gate passed."
    if status == "failed":
        return "Slice gate failed; resolve slicer errors before printing."
    if status == "warning":
        return "Slice gate returned warnings; review them before printing."
    return "Slice gate has not run yet."


def _item(
    item_id: str,
    category: str,
    title: str,
    detail: str,
    status: str,
    context: PreflightContext,
) -> dict[str, Any]:
    return {
        "id": item_id,
        "category": category,
        "title": title,
        "detail": detail,
        "status": status,
        "metadata": {
            "material": context.material,
            "printer": context.printer,
            "use_case": context.use_case,
        },
    }


__all__ = [
    "PreflightContext",
    "build_pre_print_checklist",
]
