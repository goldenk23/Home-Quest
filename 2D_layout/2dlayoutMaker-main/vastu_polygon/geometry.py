"""
Geometry for Vastu zones: 8, 16, or 32 wedges inside an arbitrary polygon.
Compass: 0° = North (up), 90° = East (right), clockwise.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import List, Optional, Sequence, Tuple

Point = Tuple[float, float]


@dataclass(frozen=True)
class VastuZone:
    name: str
    polygon: List[Point]
    label_point: Point


def _zone_angles_8() -> Sequence[Tuple[str, float, float]]:
    """8 zones: 45° each, centered on N, NE, E, SE, S, SW, W, NW."""
    return (
        ("N", 337.5, 22.5),
        ("NE", 22.5, 67.5),
        ("E", 67.5, 112.5),
        ("SE", 112.5, 157.5),
        ("S", 157.5, 202.5),
        ("SW", 202.5, 247.5),
        ("W", 247.5, 292.5),
        ("NW", 292.5, 337.5),
    )


def _zone_angles_16() -> Sequence[Tuple[str, float, float]]:
    """16 zones: 22.5° each. N, NNE, NE, ENE, E, ESE, SE, SSE, S, SSW, SW, WSW, W, WNW, NW, NNW."""
    names = (
        "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
        "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
    )
    step = 22.5
    out: List[Tuple[str, float, float]] = []
    for i, name in enumerate(names):
        start = (i * step - 11.25) % 360.0
        end = ((i + 1) * step - 11.25) % 360.0
        out.append((name, start, end))
    return tuple(out)


def _zone_angles_32() -> Sequence[Tuple[str, float, float]]:
    """
    32 zones: 11.25° each.

    Default (legacy): Vedic chakra style (centered wedges).
    """
    return _zone_angles_32_vedic()


_ZONE32_LABELS_CW: Tuple[str, ...] = (
    "N5", "N6", "N7", "N8",
    "E1", "E2", "E3", "E4", "E5", "E6", "E7", "E8",
    "S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8",
    "W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8",
    "N1", "N2", "N3", "N4",
)


def _zone_angles_32_moderne_vastu() -> Sequence[Tuple[str, float, float]]:
    """
    Moderne vastu (entrance shakti chakra) 32-pada order:
    N5..N8, E1..E8, S1..S8, W1..W8, N1..N4.

    Wedges are boundary-aligned: first boundary at 0° (North).
    """
    step = 11.25
    out: List[Tuple[str, float, float]] = []
    for idx, label in enumerate(_ZONE32_LABELS_CW):
        start = (idx * step) % 360.0
        end = ((idx + 1) * step) % 360.0
        out.append((label, start, end))
    return tuple(out)


def _zone_angles_32_vedic() -> Sequence[Tuple[str, float, float]]:
    """
    Vedic chakra style for the same 32-pada labels.

    Wedges are centered: boundaries are shifted by -5.625° (half-step) so
    the first zone is centered at 0° (North).
    """
    step = 11.25
    half = step / 2.0
    out: List[Tuple[str, float, float]] = []
    for idx, label in enumerate(_ZONE32_LABELS_CW):
        start = (idx * step - half) % 360.0
        end = ((idx + 1) * step - half) % 360.0
        out.append((label, start, end))
    return tuple(out)


class VastuPolygonGenerator:
    """
    Generates 8, 16, or 32 Vastu zone polygons by clipping the input polygon to compass wedges.
    Angles: 0° = North (up), 90° = East (right), clockwise.
    """

    ZONE_ANGLES_8 = _zone_angles_8()
    ZONE_ANGLES_16 = _zone_angles_16()
    ZONE_ANGLES_32_MODERNE_VASTU = _zone_angles_32_moderne_vastu()
    ZONE_ANGLES_32_VEDIC = _zone_angles_32_vedic()
    # Legacy: keep old attribute name used elsewhere.
    ZONE_ANGLES_32 = ZONE_ANGLES_32_VEDIC

    @classmethod
    def get_zone_angles(
        cls, zone_count: int, *, chakra_32_mode: str = "Vedic"
    ) -> Sequence[Tuple[str, float, float]]:
        if zone_count == 16:
            return cls.ZONE_ANGLES_16
        if zone_count == 32:
            if str(chakra_32_mode) == "Moderne vastu":
                return cls.ZONE_ANGLES_32_MODERNE_VASTU
            return cls.ZONE_ANGLES_32_VEDIC
        return cls.ZONE_ANGLES_8

    @classmethod
    def get_boundary_angles(
        cls, zone_count: int, *, chakra_32_mode: str = "Vedic"
    ) -> Sequence[float]:
        """Boundary ray angles in degrees for division lines (aligned with wedge boundaries)."""
        if zone_count == 8:
            return (22.5, 67.5, 112.5, 157.5, 202.5, 247.5, 292.5, 337.5)
        if zone_count == 16:
            return tuple((11.25 + 22.5 * i) % 360.0 for i in range(16))
        if zone_count == 32:
            if str(chakra_32_mode) == "Moderne vastu":
                return tuple((11.25 * i) % 360.0 for i in range(32))
            return tuple((5.625 + 11.25 * i) % 360.0 for i in range(32))
        return tuple((22.5 + 45.0 * i) % 360.0 for i in range(8))

    def __init__(self, polygon: Sequence[Point]) -> None:
        self._polygon: List[Point] = [(float(x), float(y)) for x, y in polygon]

    @staticmethod
    def _dot(a: Point, b: Point) -> float:
        return a[0] * b[0] + a[1] * b[1]

    @staticmethod
    def _sub(a: Point, b: Point) -> Point:
        return (a[0] - b[0], a[1] - b[1])

    @staticmethod
    def _add(a: Point, b: Point) -> Point:
        return (a[0] + b[0], a[1] + b[1])

    @staticmethod
    def _perp(v: Point) -> Point:
        return (v[1], -v[0])

    @staticmethod
    def angle_to_unit_vector(angle_deg: float) -> Point:
        """Compass degrees to unit vector: 0° = up => (0, -1), 90° = right => (1, 0)."""
        r = math.radians(angle_deg % 360.0)
        return (math.sin(r), -math.cos(r))

    @classmethod
    def polygon_centroid(cls, poly: Sequence[Point]) -> Optional[Point]:
        if len(poly) < 3:
            return None
        a2 = 0.0
        cx = 0.0
        cy = 0.0
        for i in range(len(poly)):
            x0, y0 = poly[i]
            x1, y1 = poly[(i + 1) % len(poly)]
            cross = x0 * y1 - x1 * y0
            a2 += cross
            cx += (x0 + x1) * cross
            cy += (y0 + y1) * cross
        if abs(a2) < 1e-9:
            return None
        cx /= (3.0 * a2)
        cy /= (3.0 * a2)
        return (cx, cy)

    @staticmethod
    def point_in_polygon(pt: Point, poly: Sequence[Point]) -> bool:
        x, y = pt
        inside = False
        n = len(poly)
        if n < 3:
            return False
        for i in range(n):
            x0, y0 = poly[i]
            x1, y1 = poly[(i + 1) % n]
            dx, dy = x1 - x0, y1 - y0
            px, py = x - x0, y - y0
            cross = dx * py - dy * px
            if abs(cross) < 1e-9:
                dot = px * dx + py * dy
                if 0.0 <= dot <= dx * dx + dy * dy + 1e-9:
                    return True
            if ((y0 > y) != (y1 > y)) and (
                x < (x1 - x0) * (y - y0) / (y1 - y0 + 1e-18) + x0
            ):
                inside = not inside
        return inside

    @classmethod
    def find_point_inside_polygon(cls, poly: Sequence[Point]) -> Optional[Point]:
        if len(poly) < 3:
            return None
        c = cls.polygon_centroid(poly)
        if c and cls.point_in_polygon(c, poly):
            return c
        ax = sum(p[0] for p in poly) / len(poly)
        ay = sum(p[1] for p in poly) / len(poly)
        if cls.point_in_polygon((ax, ay), poly):
            return (ax, ay)
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        bb = ((min(xs) + max(xs)) * 0.5, (min(ys) + max(ys)) * 0.5)
        if cls.point_in_polygon(bb, poly):
            return bb
        min_y, max_y = min(ys), max(ys)
        height = max_y - min_y
        if height < 1e-6:
            return None
        for k in range(1, 40):
            y = min_y + (k / 40.0) * height
            xs_int: List[float] = []
            for i in range(len(poly)):
                x0, y0 = poly[i]
                x1, y1 = poly[(i + 1) % len(poly)]
                if abs(y1 - y0) < 1e-12:
                    continue
                if (y0 <= y < y1) or (y1 <= y < y0):
                    t = (y - y0) / (y1 - y0)
                    xs_int.append(x0 + t * (x1 - x0))
            xs_int.sort()
            for j in range(0, len(xs_int) - 1, 2):
                x_mid = (xs_int[j] + xs_int[j + 1]) * 0.5
                if cls.point_in_polygon((x_mid, y), poly):
                    return (x_mid, y)
        return None

    @classmethod
    def _clip_polygon_half_plane(
        cls,
        poly: Sequence[Point],
        center: Point,
        line_dir: Point,
        side_sign: float,
        eps: float = 1e-9,
    ) -> List[Point]:
        if len(poly) < 3:
            return []
        n = cls._perp(line_dir)

        def signed(p: Point) -> float:
            return side_sign * cls._dot(n, cls._sub(p, center))

        def intersect(s: Point, e: Point, ds: float, de: float) -> Point:
            denom = ds - de
            if abs(denom) < 1e-18:
                return e
            t = ds / denom
            return (s[0] + (e[0] - s[0]) * t, s[1] + (e[1] - s[1]) * t)

        output: List[Point] = []
        s = poly[-1]
        ds = signed(s)
        for e in poly:
            de = signed(e)
            if ds >= -eps and de >= -eps:
                output.append(e)
            elif ds >= -eps and de < -eps:
                output.append(intersect(s, e, ds, de))
            elif ds < -eps and de >= -eps:
                output.append(intersect(s, e, ds, de))
                output.append(e)
            s, ds = e, de

        cleaned: List[Point] = []
        for p in output:
            if not cleaned or abs(p[0] - cleaned[-1][0]) > 1e-7 or abs(p[1] - cleaned[-1][1]) > 1e-7:
                cleaned.append(p)
        if len(cleaned) >= 2 and abs(cleaned[0][0] - cleaned[-1][0]) < 1e-7 and abs(cleaned[0][1] - cleaned[-1][1]) < 1e-7:
            cleaned.pop()
        return cleaned

    @classmethod
    def clip_polygon_to_wedge(
        cls, poly: Sequence[Point], center: Point, start_deg: float, end_deg: float
    ) -> List[Point]:
        if len(poly) < 3:
            return []
        delta = (end_deg - start_deg) % 360.0
        mid = (start_deg + delta * 0.5) % 360.0
        v_mid = cls.angle_to_unit_vector(mid)
        sample = cls._add(center, v_mid)
        v_start = cls.angle_to_unit_vector(start_deg)
        v_end = cls.angle_to_unit_vector(end_deg)
        n_start = cls._perp(v_start)
        n_end = cls._perp(v_end)
        sign_start = 1.0 if cls._dot(n_start, cls._sub(sample, center)) >= 0.0 else -1.0
        sign_end = 1.0 if cls._dot(n_end, cls._sub(sample, center)) >= 0.0 else -1.0
        clipped = cls._clip_polygon_half_plane(poly, center, v_start, sign_start)
        clipped = cls._clip_polygon_half_plane(clipped, center, v_end, sign_end)
        return clipped

    @classmethod
    def _safe_label_point(cls, zone_poly: Sequence[Point], fallback: Point) -> Point:
        if len(zone_poly) >= 3:
            c = cls.polygon_centroid(zone_poly)
            if c and cls.point_in_polygon(c, zone_poly):
                return c
            ax = sum(p[0] for p in zone_poly) / len(zone_poly)
            ay = sum(p[1] for p in zone_poly) / len(zone_poly)
            p = (ax, ay)
        else:
            p = fallback
        if not zone_poly or cls.point_in_polygon(p, zone_poly):
            return p if zone_poly else fallback
        t = 0.6
        for _ in range(20):
            p = (p[0] * t + fallback[0] * (1.0 - t), p[1] * t + fallback[1] * (1.0 - t))
            if cls.point_in_polygon(p, zone_poly):
                return p
            t *= 0.85
        return fallback

    @classmethod
    def clip_infinite_line_to_polygon(
        cls,
        poly: Sequence[Point],
        center: Point,
        line_dir: Point,
        eps: float = 1e-9,
    ) -> Optional[Tuple[Point, Point]]:
        if len(poly) < 3:
            return None
        cx, cy = float(center[0]), float(center[1])
        vx, vy = float(line_dir[0]), float(line_dir[1])
        if vx * vx + vy * vy < 1e-18:
            return None

        def cross(ax: float, ay: float, bx: float, by: float) -> float:
            return ax * by - ay * bx

        hits: List[Tuple[float, Point]] = []
        n = len(poly)
        for i in range(n):
            x1, y1 = poly[i]
            x2, y2 = poly[(i + 1) % n]
            ex, ey = float(x2 - x1), float(y2 - y1)
            denom = cross(vx, vy, ex, ey)
            if abs(denom) < eps:
                continue
            dx, dy = float(x1) - cx, float(y1) - cy
            t = cross(dx, dy, ex, ey) / denom
            u = cross(dx, dy, vx, vy) / denom
            if -eps <= u <= 1.0 + eps:
                hits.append((t, (cx + t * vx, cy + t * vy)))
        if len(hits) < 2:
            return None
        hits.sort(key=lambda h: h[0])
        deduped: List[Tuple[float, Point]] = []
        for t, p in hits:
            if not deduped or abs(t - deduped[-1][0]) > 1e-6:
                deduped.append((t, p))
        if len(deduped) < 2:
            return None
        return deduped[0][1], deduped[-1][1]

    def get_center_inside(self) -> Optional[Point]:
        return self.find_point_inside_polygon(self._polygon)

    def generate_zones(
        self,
        center: Optional[Point] = None,
        north_deg_offset: float = 0.0,
        zone_count: int = 8,
        chakra_32_mode: str = "Vedic",
    ) -> List[VastuZone]:
        c = center or self.get_center_inside()
        if c is None:
            return []
        angles = self.get_zone_angles(int(zone_count), chakra_32_mode=str(chakra_32_mode))
        offset = float(north_deg_offset) % 360.0
        zones: List[VastuZone] = []
        for name, start_deg, end_deg in angles:
            zpoly = self.clip_polygon_to_wedge(
                self._polygon,
                c,
                (start_deg + offset) % 360.0,
                (end_deg + offset) % 360.0,
            )
            label_pt = self._safe_label_point(zpoly, c)
            zones.append(VastuZone(name=name, polygon=zpoly, label_point=label_pt))
        return zones
