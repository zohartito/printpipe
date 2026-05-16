"""Shared material-rule registry and delta helpers."""

from __future__ import annotations

from .core import (
    MaterialRuleSet,
    get_material_rules,
    list_material_rules,
    material_delta_rows,
    merge_material_rules,
    register_material_rules,
)

__all__ = [
    "MaterialRuleSet",
    "get_material_rules",
    "list_material_rules",
    "material_delta_rows",
    "merge_material_rules",
    "register_material_rules",
]
