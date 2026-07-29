from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Sequence, Tuple

Point = Tuple[float, float]
BBox = Tuple[float, float, float, float]  # (x0, y0, x1, y1)


@dataclass(frozen=True)
class LabelPlacerConfig:
    bbox_padding_px: float = 4.0
    initial_margin_px: float = 12.0
    spiral_step_px: float = 16.0
    max_spiral_rings: int = 24


class PolygonLabelPlacer:
    """
    Places polygon measurement labels (Area/Perimeter) without overlapping other polygon labels.
    Works with a Tkinter Canvas-like API.
    """

    def __init__(self, canvas, config: Optional[LabelPlacerConfig] = None) -> None:
        self._canvas = canvas
        self._cfg = config or LabelPlacerConfig()

    def create_polygon_label(
        self,
        points: Sequence[Point],
        text: str,
        *,
        tags: Tuple[str, ...],
        fill: str = "black",
        font: Tuple[str, int] = ("Arial", 9),
    ) -> int:
        existing = self._existing_label_bboxes(exclude_group_tag=_extract_group_tag(tags))
        cx, cy = _centroid(points)

        for x, y in self._candidate_positions(points, (cx, cy)):
            text_id = self._canvas.create_text(x, y, text=text, fill=fill, font=font, tags=tags)
            bbox = self._canvas.bbox(text_id)
            if not bbox or not self._bbox_overlaps_any(_pad_bbox(bbox, self._cfg.bbox_padding_px), existing):
                return text_id
            self._canvas.delete(text_id)

        # If we couldn't find a gap (extremely dense), place at centroid.
        return self._canvas.create_text(cx, cy, text=text, fill=fill, font=font, tags=tags)

    def _existing_label_bboxes(self, *, exclude_group_tag: str | None) -> list[BBox]:
        bboxes: list[BBox] = []
        for item_id in self._canvas.find_withtag("polygon_label"):
            if exclude_group_tag:
                item_tags = self._canvas.gettags(item_id)
                if exclude_group_tag in item_tags:
                    continue
            bbox = self._canvas.bbox(item_id)
            if bbox and len(bbox) == 4:
                bboxes.append((float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])))
        return bboxes

    def _candidate_positions(self, points: Sequence[Point], centroid: Point) -> Iterable[Point]:
        minx, miny, maxx, maxy = _bbox(points)
        cx, cy = centroid
        m = float(self._cfg.initial_margin_px)

        # Centroid and a few stable positions inside the polygon bbox.
        yield (cx, cy)
        yield ((minx + maxx) / 2.0, (miny + maxy) / 2.0)
        yield ((minx + maxx) / 2.0, miny + m)
        yield ((minx + maxx) / 2.0, maxy - m)
        yield (minx + m, (miny + maxy) / 2.0)
        yield (maxx - m, (miny + maxy) / 2.0)
        yield (minx + m, miny + m)
        yield (maxx - m, miny + m)
        yield (minx + m, maxy - m)
        yield (maxx - m, maxy - m)

    @staticmethod
    def _bbox_overlaps_any(b: BBox, others: Sequence[BBox]) -> bool:
        x0, y0, x1, y1 = b
        for ox0, oy0, ox1, oy1 in others:
            if x1 <= ox0 or ox1 <= x0 or y1 <= oy0 or oy1 <= y0:
                continue
            return True
        return False


def _centroid(points: Sequence[Point]) -> Point:
    n = max(1, len(points))
    sx = 0.0
    sy = 0.0
    for x, y in points:
        sx += float(x)
        sy += float(y)
    return (sx / n, sy / n)


def _bbox(points: Sequence[Point]) -> BBox:
    xs = [float(x) for x, _ in points]
    ys = [float(y) for _, y in points]
    return (min(xs), min(ys), max(xs), max(ys))


def _pad_bbox(bbox: Sequence[float], pad: float) -> BBox:
    x0, y0, x1, y1 = bbox
    p = float(pad)
    return (float(x0) - p, float(y0) - p, float(x1) + p, float(y1) + p)


def _extract_group_tag(tags: Tuple[str, ...]) -> str | None:
    for t in tags:
        if isinstance(t, str) and t.startswith("polygon_group_"):
            return t
    return None

