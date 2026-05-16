"""Local web UI selector option catalogs."""

from __future__ import annotations

import copy
from typing import Any

_VALIDATION_STATUS = "software-foundation/unvalidated"

_PRINTER_OPTIONS: list[dict[str, Any]] = [
    {
        "id": "bambu-p2s-0-4-nozzle",
        "kind": "printer",
        "vendor": "Bambu Lab",
        "family": "P2S",
        "label": "Bambu Lab P2S (0.4 mm nozzle)",
        "description": (
            "Launch printer target for local Bambu-ready bundles. This selection records "
            "printer intent; profile loading, bed fit, and slicer gates still decide readiness."
        ),
        "printer_settings_id": "Bambu Lab P2S 0.4 nozzle",
        "printer_model": "Bambu Lab P2S",
        "nozzle_diameter_mm": 0.4,
        "build_volume_mm": {
            "x": 256,
            "y": 256,
            "z": 256,
        },
        "preflight_hints": [
            "Confirm Bambu Studio or Orca has the P2S 0.4 nozzle machine profile available.",
            "Keep the slicer gate enabled before treating a generated bundle as ready.",
        ],
        "is_launch_default": True,
    },
]

_MATERIAL_OPTIONS: list[dict[str, Any]] = [
    {
        "id": "pla",
        "kind": "material",
        "family": "PLA",
        "label": "PLA",
        "description": (
            "General PLA family foundation for low-warp local jobs. It records PLA intent "
            "without claiming brand-specific temperature or flow tuning."
        ),
        "base_profile_hint": "Generic PLA",
        "rule_source": "printpipe.materials.pla",
        "rule_id": "pla",
        "validation_status": _VALIDATION_STATUS,
        "preflight_hints": [
            "Check the spool temperature range before relying on inherited defaults.",
            "Use the slice report to review supports, thin walls, and overhang risk.",
        ],
        "is_launch_default": False,
    },
    {
        "id": "pla-plus",
        "kind": "material",
        "family": "PLA",
        "label": "PLA+",
        "description": (
            "PLA+ intent for stronger PLA-like blends. It keeps the plus choice visible "
            "while avoiding assumptions about a specific vendor blend."
        ),
        "base_profile_hint": "Generic PLA+ or Generic PLA",
        "rule_source": "printpipe.materials.pla",
        "rule_id": "pla_plus",
        "validation_status": _VALIDATION_STATUS,
        "preflight_hints": [
            "Check the spool's PLA+ temperature guidance before print-time overrides.",
            "Treat inherited PLA defaults as a starting point until the slice and part geometry are reviewed.",
        ],
        "is_launch_default": False,
    },
    {
        "id": "petg-foundation",
        "kind": "material",
        "family": "PETG",
        "label": "PETG Foundation",
        "description": (
            "Conservative PETG foundation for adhesion, stringing, cooling, and flow-control "
            "UI choices. It is a software starting point, not a product-tuned PETG promise."
        ),
        "base_profile_hint": "Generic PETG @BBL P2S",
        "rule_source": "printpipe.materials.petg",
        "rule_id": "petg-foundation",
        "validation_status": _VALIDATION_STATUS,
        "preflight_hints": [
            "Dry PETG before important prints if the spool history is unknown.",
            "Clean textured PEI and review brim/removal expectations before starting.",
        ],
        "is_launch_default": False,
    },
    {
        "id": "tpu-90a-foundation",
        "kind": "material",
        "family": "TPU",
        "label": "TPU 90A Foundation",
        "description": (
            "Soft-flex TPU 90A foundation with cautious speed, support, and cooling intent. "
            "It is meant to surface flexible-material checks before slicing."
        ),
        "base_profile_hint": "Bambu TPU 90A @BBL P2S",
        "rule_source": "printpipe.materials.tpu",
        "rule_id": "tpu-90a-foundation",
        "validation_status": _VALIDATION_STATUS,
        "preflight_hints": [
            "Use an external spool or low-drag feed path unless the exact filament is AMS-compatible.",
            "Dry TPU and disable automatic flow dynamics calibration for soft-flex baselines.",
        ],
        "is_launch_default": False,
    },
    {
        "id": "tpu-95a-foundation",
        "kind": "material",
        "family": "TPU",
        "label": "TPU 95A Foundation",
        "description": (
            "Firmer TPU 95A foundation for flexible parts that can tolerate slightly more "
            "cooling and speed than 90A TPU, pending local checks."
        ),
        "base_profile_hint": "Generic TPU or Bambu TPU @BBL P2S",
        "rule_source": "printpipe.materials.tpu",
        "rule_id": "tpu-95a-foundation",
        "validation_status": _VALIDATION_STATUS,
        "preflight_hints": [
            "Confirm the spool path is low-friction before slicing long flexible jobs.",
            "Dry TPU when spool history is unknown and review support removability.",
        ],
        "is_launch_default": False,
    },
    {
        "id": "sunlu-tpu-90a-slipper",
        "kind": "material",
        "family": "TPU",
        "label": "SUNLU TPU 90A Slipper",
        "description": (
            "Launch flexible-material option carrying the slipper-derived software lessons "
            "for SUNLU TPU 90A on P2S. It still requires local drying, feed-path, and slice checks."
        ),
        "base_profile_hint": "Bambu TPU 90A @BBL P2S",
        "rule_source": "printpipe.materials.tpu",
        "rule_id": "sunlu-tpu-90a-slipper",
        "validation_status": _VALIDATION_STATUS,
        "preflight_hints": [
            "Dry SUNLU TPU 90A at 50 C for 4-8 h before long prints.",
            "Use the external spool path and keep PTFE routing short and straight.",
            "Clean textured PEI with high-purity IPA before judging first-layer behavior.",
        ],
        "is_launch_default": True,
    },
    {
        "id": "abs",
        "kind": "material",
        "family": "ABS/ASA",
        "label": "ABS",
        "description": (
            "ABS high-temperature foundation for enclosed Bambu workflows. It surfaces "
            "chamber, brim, and ventilation checks before the run starts."
        ),
        "base_profile_hint": "Generic ABS @BBL P2S",
        "rule_source": "printpipe.materials.abs_asa",
        "rule_id": "ABS",
        "validation_status": _VALIDATION_STATUS,
        "preflight_hints": [
            "Use an enclosure and avoid drafts while the bed and chamber warm up.",
            "Confirm ventilation or filtration before running ABS locally.",
        ],
        "is_launch_default": False,
    },
    {
        "id": "asa",
        "kind": "material",
        "family": "ABS/ASA",
        "label": "ASA",
        "description": (
            "ASA high-temperature foundation for enclosed Bambu workflows. It keeps "
            "warp-control and operator environment checks visible in the selector."
        ),
        "base_profile_hint": "Generic ASA @BBL P2S",
        "rule_source": "printpipe.materials.abs_asa",
        "rule_id": "ASA",
        "validation_status": _VALIDATION_STATUS,
        "preflight_hints": [
            "Use enclosure preheat and avoid cold air movement around broad ASA parts.",
            "Confirm ventilation or filtration before starting ASA prints.",
        ],
        "is_launch_default": False,
    },
    {
        "id": "pc",
        "kind": "material",
        "family": "PC",
        "label": "PC",
        "description": (
            "Polycarbonate foundation for heat-resistant parts. It emphasizes drying, "
            "enclosure preheat, and bed-adhesion review before slicing."
        ),
        "base_profile_hint": "Generic PC @BBL P2S",
        "rule_source": "printpipe.materials.pc_pa",
        "rule_id": "PC",
        "validation_status": _VALIDATION_STATUS,
        "preflight_hints": [
            "Dry PC and keep the spool covered before printing.",
            "Use enclosure preheat and confirm the selected plate or adhesive plan.",
        ],
        "is_launch_default": False,
    },
    {
        "id": "pa",
        "kind": "material",
        "family": "PA",
        "label": "PA / Nylon",
        "description": (
            "Nylon foundation for moisture-sensitive engineering-material jobs. The UI "
            "copy highlights drying and dry-box checks before the slicer gate."
        ),
        "base_profile_hint": "Generic PA @BBL P2S",
        "rule_source": "printpipe.materials.pc_pa",
        "rule_id": "PA",
        "validation_status": _VALIDATION_STATUS,
        "preflight_hints": [
            "Dry PA immediately before printing and do not start if popping or steam appears.",
            "Feed from a dry box during the run because nylon absorbs moisture quickly.",
        ],
        "is_launch_default": False,
    },
    {
        "id": "pa-cf",
        "kind": "material",
        "family": "PA",
        "label": "PA-CF",
        "description": (
            "Carbon-fiber nylon foundation for stiff engineering-material jobs. It keeps "
            "drying, abrasive-filament hardware, and enclosure checks prominent."
        ),
        "base_profile_hint": "Generic PA-CF @BBL P2S",
        "rule_source": "printpipe.materials.pc_pa",
        "rule_id": "PA-CF",
        "validation_status": _VALIDATION_STATUS,
        "preflight_hints": [
            "Dry PA-CF immediately before printing and feed from a dry box.",
            "Use a hardened nozzle because carbon fiber is abrasive.",
            "Use enclosure preheat and review brim expectations for broad parts.",
        ],
        "is_launch_default": False,
    },
]

_DEFAULT_SELECTOR_VALUES = {
    "printer_id": "bambu-p2s-0-4-nozzle",
    "material_id": "sunlu-tpu-90a-slipper",
}


def printer_options() -> list[dict[str, Any]]:
    """Return printer selector options for the local web UI."""
    return copy.deepcopy(_PRINTER_OPTIONS)


def material_options() -> list[dict[str, Any]]:
    """Return material selector options for the local web UI."""
    return copy.deepcopy(_MATERIAL_OPTIONS)


def default_selector_values() -> dict[str, str]:
    """Return launch default selector values."""
    return dict(_DEFAULT_SELECTOR_VALUES)


def selector_catalog() -> dict[str, Any]:
    """Return the complete selector catalog for renderers."""
    return {
        "printers": printer_options(),
        "materials": material_options(),
        "defaults": default_selector_values(),
    }


__all__ = [
    "default_selector_values",
    "material_options",
    "printer_options",
    "selector_catalog",
]
