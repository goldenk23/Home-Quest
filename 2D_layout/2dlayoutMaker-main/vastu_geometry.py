"""
Backward compatibility: re-export from vastu_polygon package.
"""

from __future__ import annotations

from vastu_polygon.geometry import VastuPolygonGenerator, VastuZone

# Legacy: 8-zone angles only
VastuPolygonGenerator.ZONE_ANGLES = VastuPolygonGenerator.ZONE_ANGLES_8

__all__ = ["VastuPolygonGenerator", "VastuZone"]
