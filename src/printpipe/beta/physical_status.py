"""Physical validation status across beta run folders."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from printpipe.beta.physical import (
    PRINTED_STATUSES,
    build_physical_print_evidence,
    missing_required_evidence,
)

DEFAULT_REQUIRED_FAMILIES = ("pla", "petg", "tpu")


def build_physical_validation_status(
    runs_dir: str | Path,
    *,
    required_families: Sequence[str] = DEFAULT_REQUIRED_FAMILIES,
) -> dict[str, Any]:
    """Return whether required material families have passed physical evidence."""

    root = Path(runs_dir).expanduser().resolve()
    packets = [_packet for _packet in _load_physical_packets(root)]
    families = tuple(_normalize_family(family) for family in required_families)
    family_status = {
        family: _family_validation_status(family, packets)
        for family in families
    }
    overall_status = (
        "passed"
        if all(item["status"] == "passed" for item in family_status.values())
        else "missing_passed_evidence"
    )
    return {
        "schema_version": 1,
        "runs_dir": str(root),
        "overall_status": overall_status,
        "required_families": list(families),
        "packet_count": len(packets),
        "family_status": family_status,
    }


def render_physical_validation_status(status: dict[str, Any]) -> str:
    """Render a human-readable physical validation status report."""

    lines = [
        "PrintPipe Physical Validation",
        f"runs dir: {status.get('runs_dir', 'unknown')}",
        f"overall: {status.get('overall_status', 'unknown')}",
        "",
        "Material families:",
    ]
    family_status = status.get("family_status")
    if not isinstance(family_status, dict) or not family_status:
        lines.append("- none configured")
    else:
        for family, payload in sorted(family_status.items()):
            item = payload if isinstance(payload, dict) else {}
            line = (
                f"- {family}: {item.get('status', 'unknown')}"
                f" ({item.get('passed_count', 0)} passed / "
                f"{item.get('packet_count', 0)} packet(s))"
            )
            if item.get("missing_reason"):
                line += f" - {item['missing_reason']}"
            lines.append(line)
    lines.append("")
    return "\n".join(lines)


def _family_validation_status(
    family: str,
    packets: list[dict[str, Any]],
) -> dict[str, Any]:
    matching = [
        packet
        for packet in packets
        if packet["material_family"] == family
    ]
    passed = [
        packet
        for packet in matching
        if packet["print_status"] == "passed"
        and not packet["missing_required_evidence"]
    ]
    if passed:
        status = "passed"
        best = passed[0]
        missing_reason = ""
    elif not matching:
        status = "missing"
        best = None
        missing_reason = "no physical evidence packet found"
    elif any(packet["missing_required_evidence"] for packet in matching):
        status = "incomplete"
        best = _best_packet(matching)
        missing_reason = "physical evidence packet is missing required fields"
    else:
        status = "recorded_but_not_passed"
        best = _best_packet(matching)
        missing_reason = "no passed physical print evidence recorded"
    return {
        "status": status,
        "packet_count": len(matching),
        "printed_count": sum(
            1 for packet in matching if packet["print_status"] in PRINTED_STATUSES
        ),
        "passed_count": len(passed),
        "missing_reason": missing_reason,
        "best_evidence": best,
    }


def _load_physical_packets(runs_dir: Path) -> list[dict[str, Any]]:
    if not runs_dir.exists():
        return []
    packets: list[dict[str, Any]] = []
    for evidence_path in sorted(runs_dir.glob("*/90_physical/physical_evidence.json")):
        try:
            payload = json.loads(evidence_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        evidence = build_physical_print_evidence(
            run_id=str(payload.get("run_id", "")),
            material=str(payload.get("material", "")),
            printer=str(payload.get("printer", "")),
            object_label=str(payload.get("object_label", "")),
            print_type=str(payload.get("print_type", "")),
            print_status=str(payload.get("print_status", "")),
            operator=str(payload.get("operator", "")),
            started_at=str(payload.get("started_at", "")),
            completed_at=str(payload.get("completed_at", "")),
            slice_status=str(payload.get("slice_status", "")),
            filament_drying=str(payload.get("filament_drying", "")),
            bed_prep=str(payload.get("bed_prep", "")),
            first_layer=str(payload.get("first_layer", "")),
            adhesion=str(payload.get("adhesion", "")),
            warping=str(payload.get("warping", "")),
            stringing=str(payload.get("stringing", "")),
            layer_bonding=str(payload.get("layer_bonding", "")),
            flex_recovery=str(payload.get("flex_recovery", "")),
            support_removal=str(payload.get("support_removal", "")),
            dimensions_mm=_dict(payload.get("dimensions_mm")),
            artifacts=_list(payload.get("artifacts")),
            notes=[str(note) for note in _list(payload.get("notes"))],
        )
        packets.append(
            {
                "run_id": evidence.run_id,
                "run_root": str(evidence_path.parents[1]),
                "packet_path": str(evidence_path),
                "material": evidence.material,
                "material_family": _material_family(evidence.material),
                "printer": evidence.printer,
                "object_label": evidence.object_label,
                "print_type": evidence.print_type,
                "print_status": evidence.print_status.lower(),
                "operator": evidence.operator,
                "missing_required_evidence": missing_required_evidence(evidence),
            }
        )
    return packets


def _best_packet(packets: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not packets:
        return None
    return sorted(
        packets,
        key=lambda packet: (
            packet["print_status"] != "passed",
            len(packet["missing_required_evidence"]),
            packet["run_id"],
        ),
    )[0]


def _material_family(material: str) -> str:
    normalized = material.lower()
    if "tpu" in normalized or "flex" in normalized:
        return "tpu"
    if "petg" in normalized:
        return "petg"
    if "pla" in normalized:
        return "pla"
    return "other"


def _normalize_family(family: str) -> str:
    value = family.strip().lower()
    if not value:
        raise ValueError("required material families must not be blank")
    return value


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


__all__ = [
    "DEFAULT_REQUIRED_FAMILIES",
    "build_physical_validation_status",
    "render_physical_validation_status",
]
