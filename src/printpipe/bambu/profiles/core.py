"""Profile primitives for Bambu/Orca-style JSON presets."""

from __future__ import annotations

import copy
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Mapping

ProfileResolver = Callable[[str], Mapping[str, Any] | None]

PROFILE_ONLY_KEYS = frozenset({"inherits", "instantiation", "from", "type"})
SENTINEL_STRINGS = frozenset({"nil"})

ENUM_VALUES: dict[str, frozenset[str]] = {
    "support_style": frozenset({"default", "snug"}),
}


class EnumValidationError(ValueError):
    """Raised when a profile setting uses a value outside the known schema."""


def load_profile(path: str | Path) -> dict[str, Any]:
    """Load one JSON profile from disk."""
    profile_path = Path(path)
    with profile_path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"profile JSON must be an object: {profile_path}")
    return data


def load_profile_map(paths: list[str | Path] | tuple[str | Path, ...]) -> dict[str, dict[str, Any]]:
    """Load profiles and index them by their declared `name`."""
    profiles: dict[str, dict[str, Any]] = {}
    for path in paths:
        profile = load_profile(path)
        name = profile.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError(f"profile JSON missing string name: {path}")
        profiles[name] = profile
    return profiles


def resolve_inherits(
    starting: Mapping[str, Any],
    *,
    profiles: Mapping[str, Mapping[str, Any]] | None = None,
    resolver: ProfileResolver | None = None,
) -> dict[str, Any]:
    """Resolve an `inherits` chain and flatten root values into the leaf.

    Child keys win over parent keys. Inputs are never mutated.
    """
    if profiles is None and resolver is None:
        raise ValueError("resolve_inherits requires profiles or resolver")

    chain: list[Mapping[str, Any]] = []
    visited: set[str] = set()
    current: Mapping[str, Any] | None = starting

    while current is not None:
        name = current.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError("profile in inheritance chain is missing a string name")
        if name in visited:
            raise ValueError(f"inheritance cycle detected at {name}")
        visited.add(name)
        chain.append(current)

        parent_name = current.get("inherits")
        if parent_name in (None, ""):
            break
        if not isinstance(parent_name, str):
            raise ValueError(f"profile {name} has non-string inherits value")
        current = _resolve_parent(parent_name, profiles=profiles, resolver=resolver)

    flattened: dict[str, Any] = {}
    for profile in reversed(chain):
        _merge_profile(flattened, profile)
    return flattened


def normalize_setting_value(value: Any, *, extruder_count: int = 1) -> Any:
    """Normalize Bambu values for semantic comparisons.

    Bambu profiles often represent the same setting as a scalar, singleton
    array, duplicated per-extruder array, or numeric string with different
    precision. This helper keeps special sentinels like `nil` as strings.
    """
    if isinstance(value, list):
        normalized_items = [
            normalize_setting_value(item, extruder_count=extruder_count) for item in value
        ]
        if len(normalized_items) == 1:
            return normalized_items[0]
        if extruder_count == 1 and _all_equal(normalized_items):
            return normalized_items[0]
        return tuple(normalized_items)

    if isinstance(value, str):
        text = value.strip()
        if text in SENTINEL_STRINGS:
            return text
        if text.endswith("%"):
            number = _decimal_or_none(text[:-1].strip())
            if number is not None:
                return ("percent", number.normalize())
        number = _decimal_or_none(text)
        if number is not None:
            return number.normalize()
        return text

    if isinstance(value, float):
        return Decimal(str(value)).normalize()
    if isinstance(value, int) and not isinstance(value, bool):
        return Decimal(value).normalize()
    if isinstance(value, dict):
        return tuple(
            sorted(
                (
                    key,
                    normalize_setting_value(item, extruder_count=extruder_count),
                )
                for key, item in value.items()
            )
        )
    return value


def settings_equal(left: Any, right: Any, *, extruder_count: int = 1) -> bool:
    """Return True when two Bambu setting values are semantically equal."""
    return normalize_setting_value(left, extruder_count=extruder_count) == normalize_setting_value(
        right,
        extruder_count=extruder_count,
    )


def generate_settings_delta_rows(
    defaults: Mapping[str, Any],
    custom: Mapping[str, Any],
    *,
    categories: Mapping[str, str] | None = None,
    reasons: Mapping[str, str] | None = None,
    extruder_count: int = 1,
) -> list[dict[str, Any]]:
    """Generate report rows for semantic setting changes."""
    category_map = categories or {}
    reason_map = reasons or {}
    rows: list[dict[str, Any]] = []

    for key in sorted(set(defaults) | set(custom)):
        default = defaults.get(key)
        custom_value = custom.get(key)
        if settings_equal(default, custom_value, extruder_count=extruder_count):
            continue
        rows.append(
            {
                "key": key,
                "default": copy.deepcopy(default),
                "custom": copy.deepcopy(custom_value),
                "category": category_map.get(key, "behavior"),
                "reason": reason_map.get(key, "reason not assigned"),
            }
        )
    return rows


def validate_enum_value(key: str, value: Any) -> str:
    """Validate one enum setting value and return its normalized scalar string."""
    if key not in ENUM_VALUES:
        raise KeyError(f"no enum schema registered for {key}")

    normalized = normalize_setting_value(value)
    if not isinstance(normalized, str):
        raise EnumValidationError(f"{key} must be one of {sorted(ENUM_VALUES[key])}; got {value!r}")
    if normalized not in ENUM_VALUES[key]:
        raise EnumValidationError(
            f"{key} must be one of {sorted(ENUM_VALUES[key])}; got {normalized!r}"
        )
    return normalized


def _resolve_parent(
    parent_name: str,
    *,
    profiles: Mapping[str, Mapping[str, Any]] | None,
    resolver: ProfileResolver | None,
) -> Mapping[str, Any]:
    if resolver is not None:
        resolved = resolver(parent_name)
        if resolved is not None:
            return resolved
    if profiles is not None and parent_name in profiles:
        return profiles[parent_name]
    raise KeyError(f"profile parent not found: {parent_name}")


def _merge_profile(target: dict[str, Any], profile: Mapping[str, Any]) -> None:
    for key, value in profile.items():
        if key in PROFILE_ONLY_KEYS:
            continue
        if isinstance(value, Mapping) and isinstance(target.get(key), dict):
            merged = copy.deepcopy(target[key])
            _merge_profile(merged, value)
            target[key] = merged
        else:
            target[key] = copy.deepcopy(value)


def _decimal_or_none(text: str) -> Decimal | None:
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _all_equal(items: list[Any]) -> bool:
    if not items:
        return False
    first = items[0]
    return all(item == first for item in items[1:])
