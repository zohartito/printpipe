"""Conservative PLA material rule foundation."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class MaterialRuleSet:
    """Profile override bundle for one material-family intent."""

    variant: str
    profile_intent: str
    filament_overrides: Mapping[str, Any]
    process_overrides: Mapping[str, Any]
    reasons: Mapping[str, str]
    categories: Mapping[str, str]


_BASE_PROCESS_OVERRIDES = {
    "layer_height": ["0.20"],
    "wall_loops": ["2"],
}

_BASE_PROCESS_REASONS = {
    "layer_height": "Use the common 0.20 mm process intent as a broad PLA starting point.",
    "wall_loops": "Keep the conservative two-wall baseline until object strength rules choose otherwise.",
}

_BASE_PROCESS_CATEGORIES = {
    "layer_height": "compatibility",
    "wall_loops": "compatibility",
}

PLA_RULES: dict[str, MaterialRuleSet] = {
    "pla": MaterialRuleSet(
        variant="pla",
        profile_intent=(
            "Clone a Generic PLA filament/process baseline and apply only material-family "
            "identity plus conservative compatibility intent."
        ),
        filament_overrides={
            "filament_type": ["PLA"],
            "filament_vendor": ["Generic"],
        },
        process_overrides=_BASE_PROCESS_OVERRIDES,
        reasons={
            "filament_type": "Declare the material family as PLA for Bambu-compatible profile selection.",
            "filament_vendor": "Use a neutral vendor label because no brand-specific PLA tuning is validated.",
            **_BASE_PROCESS_REASONS,
        },
        categories={
            "filament_type": "metadata",
            "filament_vendor": "metadata",
            **_BASE_PROCESS_CATEGORIES,
        },
    ),
    "pla_plus": MaterialRuleSet(
        variant="pla_plus",
        profile_intent=(
            "Clone a Generic PLA+ or PLA Tough baseline when available; otherwise keep Generic PLA "
            "defaults and record the PLA+ material intent without printer-specific tuning claims."
        ),
        filament_overrides={
            "filament_type": ["PLA"],
            "filament_vendor": ["Generic PLA+"],
        },
        process_overrides=_BASE_PROCESS_OVERRIDES,
        reasons={
            "filament_type": "Represent PLA+ as the PLA material family while retaining the plus intent in metadata.",
            "filament_vendor": "Mark PLA+ intent generically because brand-specific temperature and flow tuning is unvalidated.",
            **_BASE_PROCESS_REASONS,
        },
        categories={
            "filament_type": "metadata",
            "filament_vendor": "metadata",
            **_BASE_PROCESS_CATEGORIES,
        },
    ),
}

_VARIANT_ALIASES = {
    "pla": "pla",
    "generic_pla": "pla",
    "pla+": "pla_plus",
    "pla_plus": "pla_plus",
    "plus": "pla_plus",
}


def build_pla_overrides(variant: str = "pla") -> dict[str, Any]:
    """Return copy-safe PLA overrides plus reasons for settings receipts."""

    normalized_variant = _normalize_variant(variant)
    rule = PLA_RULES[normalized_variant]
    return {
        "variant": rule.variant,
        "profile_intent": rule.profile_intent,
        "filament_overrides": copy.deepcopy(dict(rule.filament_overrides)),
        "process_overrides": copy.deepcopy(dict(rule.process_overrides)),
        "reasons": dict(rule.reasons),
        "categories": dict(rule.categories),
    }


def _normalize_variant(variant: str) -> str:
    normalized = variant.strip().lower().replace("-", "_").replace(" ", "_")
    if normalized in _VARIANT_ALIASES:
        return _VARIANT_ALIASES[normalized]
    supported = ", ".join(sorted(PLA_RULES))
    raise ValueError(f"unsupported PLA variant {variant!r}; supported variants: {supported}")
