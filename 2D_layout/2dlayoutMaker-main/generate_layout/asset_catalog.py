"""Phase 10 core: one asset catalog as the source of truth for AI furniture.

Reconciles two existing sources that must never drift apart:
- ``ai_validator.FURNITURE``      — the exact allowlist a layout is validated against.
- ``FurnitureHelper.furniture_sizes`` — the physical footprints autofix/placement use.

For each allowlisted asset it resolves a footprint (via the same normalization the validator
and autofix use) and a set of room roles, so a deterministic furniture placer (next slice)
and prompt/validator allowlists can all be generated from here instead of hand-maintained
lists. Keeping missing assets explicit is a hard rule: an unresolved asset is reported, never
silently swapped for a sofa.

Offline-testable: ``python -m generate_layout.asset_catalog``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .ai_validator import FURNITURE

try:  # same source the validator/autofix read; keep footprints consistent.
    from FurnitureHelper.furniture_sizes import STANDARD_FURNITURE_SIZES
except Exception:  # noqa: BLE001 - catalog must degrade gracefully, not crash imports
    STANDARD_FURNITURE_SIZES = {}


def _key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


_SIZE_BY_KEY = {_key(k): v for k, v in STANDARD_FURNITURE_SIZES.items()}

# Room role assignment by keyword on the normalized asset key. An asset may serve several
# roles (a wardrobe suits bedrooms and storage). Doors are structural, not furniture.
_ROLE_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("door", ("door",)),
    ("bed", ("bedroom",)),
    ("wardrobe", ("bedroom", "storage")),
    ("standingcabinet", ("bedroom", "office", "storage")),
    ("sofa", ("living",)),
    ("tv", ("living",)),
    ("coffeetable", ("living",)),
    ("diningtable", ("dining",)),
    ("tablechairset", ("dining",)),
    ("studytablechair", ("office",)),
    ("desk", ("office",)),
    ("chair", ("living", "dining", "office")),
    ("kitchenplatform", ("kitchen",)),
    ("stove", ("kitchen",)),
    ("sink", ("kitchen",)),
    ("fridge", ("kitchen",)),
    ("toilet", ("bathroom",)),
    ("bathtub", ("bathroom",)),
    ("shower", ("bathroom",)),
    ("washbasin", ("bathroom",)),
    ("blackbox", ("storage",)),
)


@dataclass(frozen=True)
class Asset:
    name: str                      # canonical name exactly as the validator allows it
    key: str                       # normalized lookup key
    dims_ft: tuple[float, float] | None  # (length, width) in feet, or None if unknown
    roles: tuple[str, ...] = field(default_factory=tuple)
    is_door: bool = False


def _roles_for(key: str) -> tuple[str, ...]:
    roles: list[str] = []
    for needle, rs in _ROLE_KEYWORDS:
        if needle in key:
            for r in rs:
                if r not in roles:
                    roles.append(r)
    return tuple(roles)


def build_catalog() -> dict[str, Asset]:
    """Build the canonical catalog keyed by the validator's exact asset name."""
    catalog: dict[str, Asset] = {}
    for name in sorted(FURNITURE):
        key = _key(name)
        roles = _roles_for(key)
        is_door = "door" in key
        catalog[name] = Asset(name=name, key=key, dims_ft=_SIZE_BY_KEY.get(key),
                              roles=roles, is_door=is_door)
    return catalog


CATALOG = build_catalog()


def dimensions(name: str) -> tuple[float, float] | None:
    asset = CATALOG.get(name)
    if asset and asset.dims_ft:
        return asset.dims_ft
    return _SIZE_BY_KEY.get(_key(name))


def assets_for_role(role: str) -> list[str]:
    """Allowlisted, dimensioned assets usable in a room of the given role."""
    return [a.name for a in CATALOG.values() if role in a.roles and a.dims_ft and not a.is_door]


def is_supported(name: str) -> bool:
    return name in CATALOG


def unresolved_assets() -> list[str]:
    """Allowlisted non-door assets that have no footprint (a catalog gap to fix)."""
    return sorted(a.name for a in CATALOG.values() if not a.is_door and a.dims_ft is None)


if __name__ == "__main__":
    # ponytail: the runnable guard — the allowlist and the footprint table must agree, and
    # the common room roles must each have at least one usable asset.
    missing = unresolved_assets()
    assert not missing, f"allowlisted assets without a footprint: {missing}"
    for role in ("bedroom", "kitchen", "bathroom", "living", "dining", "office"):
        options = assets_for_role(role)
        assert options, f"no catalog assets for role {role}"
    # doors are catalogued but excluded from furnishable role sets
    assert CATALOG["singlehand_door"].is_door
    assert "singlehand_door" not in assets_for_role("living")
    print(f"asset_catalog self-check passed: {len(CATALOG)} assets, 0 unresolved")
    print("  bedroom:", assets_for_role("bedroom"))
    print("  kitchen:", assets_for_role("kitchen"))
