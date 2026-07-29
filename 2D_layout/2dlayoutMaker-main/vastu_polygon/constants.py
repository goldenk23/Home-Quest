"""
Constants for Vastu polygon: zone count options and light/translucent fill colors.
"""

from __future__ import annotations

# Dropdown choices: (display_label, zone_count)
ZONE_COUNT_CHOICES = [
    ("8 zone", 8),
    ("16 zone", 16),
    ("32 zone", 32),
]

DEFAULT_ZONE_COUNT = 8

# Light, translucent-style fill colors (same hue, lighter shade) for zone polygons.
# Tkinter has no alpha; use pastel/light shades so layout stays visible.
ZONE_FILL_COLORS_8 = [
    "#fce4ec", "#f8bbd9", "#f48fb1", "#f06292",
    "#e91e63", "#ad1457", "#880e4f", "#4a148c",
]
# Extended palettes for 16 and 32 zones (cycled)
ZONE_FILL_COLORS_16 = [
    "#fce4ec", "#f8bbd9", "#f48fb1", "#f06292", "#ec407a", "#e91e63", "#d81b60", "#c2185b",
    "#ad1457", "#880e4f", "#6a1b9a", "#7b1fa2", "#8e24aa", "#9c27b0", "#ab47bc", "#ba68c8",
]
ZONE_FILL_COLORS_32 = [
    "#fce4ec", "#fad6e0", "#f8bbd9", "#f6a0d2", "#f48fb1", "#f27ea0", "#f06292", "#ee5184",
    "#ec407a", "#ea2f70", "#e91e63", "#d81b60", "#c7185d", "#b6155a", "#ad1457", "#9f1254",
    "#880e4f", "#7a0c4a", "#6a1b9a", "#7b1fa2", "#8e24aa", "#9c27b0", "#ab47bc", "#ba68c8",
    "#ce93d8", "#e1bee7", "#f3e5f5", "#f8e0f0", "#fad6e8", "#fce4ec", "#fdd8e6", "#fee0eb",
]
