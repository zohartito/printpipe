"""Generic material rule-set registry and delta helpers."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Literal, Mapping

from printpipe.bambu.profiles.core import generate_settings_delta_rows

ProfileScope = Literal["filament", "process"]


@dataclass(frozen=True)
class MaterialRuleSet:
    """Material-family profile overrides plus their receipt annotations."""

    material_id: str
    display_name: str
    base_profile_hint: str | None = None
    filament_overrides: Mapping[str, Any] = field(default_factory=dict)
    process_overrides: Mapping[str, Any] = field(default_factory=dict)
    reasons: Mapping[str, str] = field(default_factory=dict)
    categories: Mapping[str, str] = field(default_factory=dict)
    preflight_notes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        material_id = self.material_id.strip()
        display_name = self.display_name.strip()
        if not material_id:
            raise ValueError("material_id is required")
        if not display_name:
            raise ValueError("display_name is required")

        object.__setattr__(self, "material_id", material_id)
        object.__setattr__(self, "display_name", display_name)
        object.__setattr__(self, "filament_overrides", dict(self.filament_overrides))
        object.__setattr__(self, "process_overrides", dict(self.process_overrides))
        object.__setattr__(self, "reasons", dict(self.reasons))
        object.__setattr__(self, "categories", dict(self.categories))
        object.__setattr__(self, "preflight_notes", tuple(self.preflight_notes))


_REGISTRY: dict[str, MaterialRuleSet] = {}


def register_material_rules(
    rule_set: MaterialRuleSet,
    *,
    replace: bool = False,
) -> MaterialRuleSet:
    """Register a material rule set by `material_id`."""
    if not isinstance(rule_set, MaterialRuleSet):
        raise TypeError("rule_set must be a MaterialRuleSet")
    if rule_set.material_id in _REGISTRY and not replace:
        raise ValueError(f"material rule set already registered: {rule_set.material_id}")
    _REGISTRY[rule_set.material_id] = rule_set
    return rule_set


def get_material_rules(material_id: str) -> MaterialRuleSet:
    """Return one registered material rule set."""
    try:
        return _REGISTRY[material_id]
    except KeyError as exc:
        raise KeyError(f"unknown material rule set: {material_id}") from exc


def list_material_rules() -> list[MaterialRuleSet]:
    """Return registered material rule sets sorted by stable material id."""
    return [_REGISTRY[material_id] for material_id in sorted(_REGISTRY)]


def merge_material_rules(
    defaults: Mapping[str, Any],
    rule_set: MaterialRuleSet,
    *,
    profile_scope: ProfileScope,
) -> dict[str, Any]:
    """Merge scoped material overrides onto profile defaults without mutation."""
    merged = copy.deepcopy(dict(defaults))
    for key, value in _overrides_for_scope(rule_set, profile_scope).items():
        merged[key] = copy.deepcopy(value)
    return merged


def material_delta_rows(
    defaults: Mapping[str, Any],
    rule_set: MaterialRuleSet,
    *,
    profile_scope: ProfileScope,
    extruder_count: int = 1,
) -> list[dict[str, Any]]:
    """Generate annotated settings delta rows for one material profile scope."""
    rows = generate_settings_delta_rows(
        defaults,
        merge_material_rules(defaults, rule_set, profile_scope=profile_scope),
        categories=_annotations_for_scope(rule_set.categories, profile_scope),
        reasons=_annotations_for_scope(rule_set.reasons, profile_scope),
        extruder_count=extruder_count,
    )
    for row in rows:
        row["profile_scope"] = profile_scope
        row["material_id"] = rule_set.material_id
    return rows


def _overrides_for_scope(
    rule_set: MaterialRuleSet,
    profile_scope: ProfileScope,
) -> Mapping[str, Any]:
    if profile_scope == "filament":
        return rule_set.filament_overrides
    if profile_scope == "process":
        return rule_set.process_overrides
    raise ValueError(f"unsupported material profile scope: {profile_scope}")


def _annotations_for_scope(
    annotations: Mapping[str, str],
    profile_scope: ProfileScope,
) -> dict[str, str]:
    scoped_prefix = f"{profile_scope}."
    scoped: dict[str, str] = {}
    unscoped: dict[str, str] = {}

    for key, value in annotations.items():
        if key.startswith(scoped_prefix):
            scoped[key.removeprefix(scoped_prefix)] = value
        elif "." not in key:
            unscoped[key] = value

    return {**unscoped, **scoped}
