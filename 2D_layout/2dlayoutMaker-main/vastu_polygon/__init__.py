"""
Vastu polygon package: geometry and drawing for 8/16/32 zone overlays on user-drawn polygons.
North is oriented to the right by default to match app conventions.
"""

from __future__ import annotations

from vastu_polygon.geometry import VastuPolygonGenerator, VastuZone
from vastu_polygon.constants import ZONE_COUNT_CHOICES, DEFAULT_ZONE_COUNT

__all__ = [
    "VastuPolygonGenerator",
    "VastuZone",
    "ZONE_COUNT_CHOICES",
    "DEFAULT_ZONE_COUNT",
]
