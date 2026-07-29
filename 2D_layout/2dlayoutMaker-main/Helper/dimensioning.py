from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple


Point = Tuple[float, float]


@dataclass(frozen=True)
class DimensionStyle:
    # How far the dimension line is offset from the actual edge
    offset_px: float = 18.0

    # Extension line behaviour
    show_extension_lines: bool = False
    extension_overhang_px: float = 2.0
    extension_gap_from_object_px: float = 2.0
    extension_color: str = "#000000"
    extension_dash: Optional[Tuple[int, int]] = None
    extension_width: float = 1.0

    # Dimension line behaviour
    dim_color: str = "#000000"
    dim_width: float = 1.0
    arrowshape: Tuple[int, int, int] = (10, 12, 4)
    min_edge_length_px: float = 6.0

    # Text behaviour
    # Note: rotated text is attempted via `angle` option; falls back silently if unsupported.
    text_fill: str = "#000000"
    text_font: Tuple[str, int] = ("Arial", 11)
    text_offset_px: float = 0.0  # keep label on the dimension line by default
    # If True, text is flipped 180° to avoid upside-down labels.
    # Changed from False to True as per user request to keep measurement labels upright.
    text_keep_upright: bool = True
    text_gap_padding_px: float = 6.0  # break-line padding around text
    # If True, draws a small background plate behind the label.
    # Default False because you asked to "cut the line" instead of filling behind text.
    text_bg_enabled: bool = False
    text_bg_pad_px: float = 2.0
    text_rotation_backend: str = "pil"  # "pil" | "tk"

    # When splitting the dimension line to create a gap under text, we use two
    # segments so arrowheads remain at both ends.
    arrow_at_start: str = "first"
    arrow_at_end: str = "last"


class DimensionDrawer:
    """
    Draws simple engineering-style dimensions for polygon edges:
    - extension lines from each vertex
    - a dimension line parallel to the edge with arrowheads on both ends
    - a length label at the center of the dimension line

    Designed to work with a Tkinter Canvas-like API (create_line/create_text/etc.).
    """

    def __init__(self, canvas, model, style: Optional[DimensionStyle] = None) -> None:
        self._canvas = canvas
        self._model = model
        self._style = style or DimensionStyle()
        # Keep references to PhotoImage objects, otherwise Tk will GC them.
        self._image_refs_by_dim_tag: dict[str, List[object]] = {}

    def clear_dimensions_for_group(self, dim_tag: str) -> None:
        """Remove previously drawn dimension items for the provided dimension tag."""
        try:
            for item_id in self._canvas.find_withtag(dim_tag):
                try:
                    self._canvas.delete(item_id)
                except Exception:
                    continue
        except Exception:
            # If canvas doesn't support find_withtag, do nothing.
            return
        # Also release any stored image refs for this tag
        try:
            self._image_refs_by_dim_tag.pop(dim_tag, None)
        except Exception:
            pass

    def draw_polygon_edge_dimensions(
        self,
        points: Sequence[Point],
        *,
        group_tag: str,
        dim_tag: Optional[str] = None,
        style_override: Optional[DimensionStyle] = None,
    ) -> List[int]:
        """
        Draw dimensions for each edge in polygon `points` (assumed closed implicitly).
        Returns a list of created canvas item ids.
        """
        pts = list(points)
        if len(pts) < 3:
            return []

        active_style = style_override or self._style
        created: List[int] = []
        c = _avg_centroid(pts)
        used_dim_tag = dim_tag or f"{group_tag}__dims"

        # Replace any previous dimensions for this group
        self.clear_dimensions_for_group(used_dim_tag)

        n = len(pts)
        for i in range(n):
            edge_tag = f"{used_dim_tag}_edge_{i}"
            created.extend(self.draw_single_edge_dimension(
                pts[i], 
                pts[(i + 1) % n], 
                c, 
                group_tag=group_tag, 
                dim_tag=edge_tag,
                parent_dim_tag=used_dim_tag,
                style_override=active_style
            ))

        return created

    def draw_single_edge_dimension(
        self,
        p0: Point,
        p1: Point,
        centroid: Point,
        *,
        group_tag: str,
        dim_tag: str,
        parent_dim_tag: Optional[str] = None,
        style_override: Optional[DimensionStyle] = None,
    ) -> List[int]:
        """Draw dimensions for a single edge. Used for procedural redraws (undo/redo)."""
        active_style = style_override or self._style
        created: List[int] = []
        
        seg = _sub(p1, p0)
        seg_len = math.hypot(seg[0], seg[1])
        if seg_len < float(active_style.min_edge_length_px):
            return []
        
        # Aggregate all tags for this edge item
        all_tags_list = [group_tag, dim_tag, "dimension_item"]
        if parent_dim_tag:
            all_tags_list.append(parent_dim_tag)
        all_tags = tuple(all_tags_list)

        normal = _choose_outward_normal(p0, p1, centroid, active_style.offset_px)
        p0_off = _add(p0, _mul(normal, active_style.offset_px))
        p1_off = _add(p1, _mul(normal, active_style.offset_px))

        # Optional extension lines
        ext_ids: List[int] = []
        if active_style.show_extension_lines:
            p0_ext = _add(p0_off, _mul(normal, active_style.extension_overhang_px))
            p1_ext = _add(p1_off, _mul(normal, active_style.extension_overhang_px))
            p0_ext_start = _add(p0, _mul(normal, active_style.extension_gap_from_object_px))
            p1_ext_start = _add(p1, _mul(normal, active_style.extension_gap_from_object_px))

            ext0 = self._canvas.create_line(
                p0_ext_start[0], p0_ext_start[1],
                p0_ext[0], p0_ext[1],
                fill=active_style.extension_color,
                width=active_style.extension_width,
                dash=active_style.extension_dash,
                tags=all_tags + ("dimension_extension",),
            )
            ext1 = self._canvas.create_line(
                p1_ext_start[0], p1_ext_start[1],
                p1_ext[0], p1_ext[1],
                fill=active_style.extension_color,
                width=active_style.extension_width,
                dash=active_style.extension_dash,
                tags=all_tags + ("dimension_extension",),
            )
            ext_ids.extend([ext0, ext1])
            created.extend(ext_ids)

        # Dimension label
        label = self._format_length(seg_len)
        mx, my = (p0_off[0] + p1_off[0]) / 2.0, (p0_off[1] + p1_off[1]) / 2.0
        tx, ty = _add((mx, my), _mul(normal, active_style.text_offset_px))
        angle_deg = _segment_angle_deg(p0_off, p1_off)
        if active_style.text_keep_upright:
            angle_deg = _upright_text_angle(angle_deg)

        text_id = self._create_dimension_label(
            tx, ty, label, angle_deg,
            tags=all_tags + ("dimension_label",),
            dim_tag=parent_dim_tag or dim_tag,
            style_override=active_style,
        )
        created.append(text_id)

        # Dimension line with arrows
        dir_u = _unit_direction(p0_off, p1_off)
        gap_half = self._estimate_gap_half_px(text_id) + float(active_style.text_gap_padding_px)

        dim_line_ids: List[int] = []
        if gap_half * 2.0 >= seg_len * 0.75:
            dim0 = self._canvas.create_line(
                p0_off[0], p0_off[1], p1_off[0], p1_off[1],
                fill=active_style.dim_color,
                width=active_style.dim_width,
                arrow="both",
                arrowshape=active_style.arrowshape,
                tags=all_tags + ("dimension_line",),
            )
            created.append(dim0)
            dim_line_ids.append(dim0)
        else:
            left_end = _add((mx, my), _mul(dir_u, -gap_half))
            right_start = _add((mx, my), _mul(dir_u, gap_half))

            dim_a = self._canvas.create_line(
                p0_off[0], p0_off[1], left_end[0], left_end[1],
                fill=active_style.dim_color,
                width=active_style.dim_width,
                arrow=active_style.arrow_at_start,
                arrowshape=active_style.arrowshape,
                tags=all_tags + ("dimension_line",),
            )
            dim_b = self._canvas.create_line(
                right_start[0], right_start[1], p1_off[0], p1_off[1],
                fill=active_style.dim_color,
                width=active_style.dim_width,
                arrow=active_style.arrow_at_end,
                arrowshape=active_style.arrowshape,
                tags=all_tags + ("dimension_line",),
            )
            created.extend([dim_a, dim_b])
            dim_line_ids.extend([dim_a, dim_b])

        # Optional background plate
        bg_id = None
        if active_style.text_bg_enabled:
            try:
                bbox = self._canvas.bbox(text_id)
                if bbox and len(bbox) == 4:
                    pad = float(active_style.text_bg_pad_px)
                    bg = self._get_canvas_bg_color()
                    bg_id = self._canvas.create_rectangle(
                        bbox[0] - pad, bbox[1] - pad,
                        bbox[2] + pad, bbox[3] + pad,
                        fill=bg, outline="",
                        tags=all_tags + ("dimension_text_bg",),
                    )
                    created.append(bg_id)
            except Exception: pass

        # Z-order
        try:
            for _eid in ext_ids: self._canvas.tag_raise(_eid)
            for _lid in dim_line_ids: self._canvas.tag_raise(_lid)
            if bg_id is not None: self._canvas.tag_raise(bg_id)
            self._canvas.tag_raise(text_id)
        except Exception: pass

        return created

        return created

    def _format_length(self, pixel_length: float) -> str:
        """
        Convert pixel length to model units.
        Uses the same idea as the rest of the app:
        - pixels -> (pixels / (grid_spacing * zoom_level)) => feet-units
        - multiply by UNIT_SCALE for selected unit
        """
        zoom = float(getattr(self._model, "zoom_level", 1.0) or 1.0)
        grid_spacing = float(getattr(self._model, "grid_spacing", 20.0) or 20.0)
        unit = getattr(self._model, "unit", "ft")
        unit_scale_map = getattr(self._model, "unit_scale", {}) or {}
        unit_factor = float(unit_scale_map.get(unit, 1.0) or 1.0)

        denom = max(1e-6, grid_spacing * zoom)
        real = (float(pixel_length) / denom) * unit_factor
        return f"{real:.2f} {unit}"

    def _get_canvas_bg_color(self) -> str:
        """Best-effort: match canvas background for the text plate."""
        try:
            return str(self._canvas.cget("bg"))
        except Exception:
            try:
                return str(self._canvas.cget("background"))
            except Exception:
                return "#F3F4F6"

    def _estimate_gap_half_px(self, text_id: int) -> float:
        """
        Estimate half-gap length (in pixels) needed to "break" the dimension line
        behind the text. Uses canvas bbox which is axis-aligned.
        """
        try:
            bbox = self._canvas.bbox(text_id)
        except Exception:
            bbox = None
        if not bbox or len(bbox) != 4:
            return 18.0
        w = float(abs(bbox[2] - bbox[0]))
        h = float(abs(bbox[3] - bbox[1]))
        return max(w, h) / 2.0

    def _create_dimension_label(
        self,
        x: float,
        y: float,
        text: str,
        angle_deg: float,
        *,
        tags: Tuple[str, ...],
        dim_tag: str,
        style_override: Optional[DimensionStyle] = None,
    ) -> int:
        """
        Create a rotated label. Tk's `create_text(angle=...)` support is not consistent
        across platforms/builds; using PIL gives consistent rotation everywhere.
        """
        active_style = style_override or self._style
        backend = str(getattr(active_style, "text_rotation_backend", "pil") or "pil").lower()
        if backend == "tk":
            try:
                return self._canvas.create_text(
                    x,
                    y,
                    text=text,
                    fill=active_style.text_fill,
                    font=active_style.text_font,
                    angle=angle_deg,
                    tags=tags,
                )
            except Exception:
                # fall through to PIL
                backend = "pil"

        # PIL backend
        try:
            from PIL import Image, ImageDraw, ImageFont, ImageTk  # type: ignore
        except Exception:
            # absolute fallback: unrotated text
            return self._canvas.create_text(
                x,
                y,
                text=text,
                fill=active_style.text_fill,
                font=active_style.text_font,
                tags=tags,
            )

        font_name, font_size = active_style.text_font
        pil_font = None
        # Try a few common fonts; fallback to default for cross-platform safety.
        for candidate in (
            "arial.ttf",
            "Arial.ttf",
            "DejaVuSans.ttf",
            "LiberationSans-Regular.ttf",
        ):
            try:
                pil_font = ImageFont.truetype(candidate, int(font_size))
                break
            except Exception:
                pil_font = None
        if pil_font is None:
            try:
                pil_font = ImageFont.load_default()
            except Exception:
                pil_font = None

        # Measure text
        dummy = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        draw = ImageDraw.Draw(dummy)
        if pil_font is not None:
            bbox = draw.textbbox((0, 0), text, font=pil_font)
        else:
            bbox = draw.textbbox((0, 0), text)
        tw = max(1, int(bbox[2] - bbox[0]))
        th = max(1, int(bbox[3] - bbox[1]))

        pad = 2
        img = Image.new("RGBA", (tw + pad * 2, th + pad * 2), (0, 0, 0, 0))
        d2 = ImageDraw.Draw(img)
        fill = self._style.text_fill
        try:
            d2.text((pad, pad), text, fill=fill, font=pil_font)
        except Exception:
            d2.text((pad, pad), text, fill=fill)

        # PIL rotates counter-clockwise; this aligns with our computed segment angle.
        rot = img.rotate(angle_deg, expand=True, resample=Image.BICUBIC)
        photo = ImageTk.PhotoImage(rot)

        try:
            self._image_refs_by_dim_tag.setdefault(dim_tag, []).append(photo)
        except Exception:
            pass

        return self._canvas.create_image(
            x,
            y,
            image=photo,
            anchor="center",
            tags=tags,
        )


def _avg_centroid(pts: Sequence[Point]) -> Point:
    sx = 0.0
    sy = 0.0
    n = max(1, len(pts))
    for x, y in pts:
        sx += float(x)
        sy += float(y)
    return (sx / n, sy / n)


def _choose_outward_normal(p0: Point, p1: Point, centroid: Point, offset_px: float) -> Point:
    dx = float(p1[0] - p0[0])
    dy = float(p1[1] - p0[1])
    seg_len = math.hypot(dx, dy)
    if seg_len <= 1e-6:
        return (0.0, -1.0)

    # Two candidate normals
    nx1, ny1 = (-dy / seg_len, dx / seg_len)
    nx2, ny2 = (-nx1, -ny1)

    mx, my = (float(p0[0] + p1[0]) / 2.0, float(p0[1] + p1[1]) / 2.0)
    cdx, cdy = float(mx - centroid[0]), float(my - centroid[1])

    # Choose the normal that moves further away from centroid
    d1 = (cdx + nx1 * offset_px) ** 2 + (cdy + ny1 * offset_px) ** 2
    d2 = (cdx + nx2 * offset_px) ** 2 + (cdy + ny2 * offset_px) ** 2
    return (nx1, ny1) if d1 >= d2 else (nx2, ny2)


def _add(a: Point, b: Point) -> Point:
    return (float(a[0] + b[0]), float(a[1] + b[1]))


def _sub(a: Point, b: Point) -> Point:
    return (float(a[0] - b[0]), float(a[1] - b[1]))


def _mul(v: Point, s: float) -> Point:
    return (float(v[0] * s), float(v[1] * s))


def _segment_angle_deg(p0: Point, p1: Point) -> float:
    dx = float(p1[0] - p0[0])
    dy = float(p1[1] - p0[1])
    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
        return 0.0
    # Canvas uses y-down coordinates. To get a visually-correct CCW angle for rotation
    # (matching how PIL/Tk interpret "positive = counter-clockwise" on screen),
    # we use (-dy).
    return float(math.degrees(math.atan2(-dy, dx)))


def _upright_text_angle(angle_deg: float) -> float:
    """
    Keep text readable (avoid upside-down labels) by normalizing angle to [-180, 180]
    and flipping 180° when it would be upside down.
    """
    a = float(angle_deg)
    while a <= -180.0:
        a += 360.0
    while a > 180.0:
        a -= 360.0
    if a > 90.0 or a < -90.0:
        a += 180.0
    while a <= -180.0:
        a += 360.0
    while a > 180.0:
        a -= 360.0
    return a


def _unit_direction(p0: Point, p1: Point) -> Point:
    dx = float(p1[0] - p0[0])
    dy = float(p1[1] - p0[1])
    L = math.hypot(dx, dy)
    if L <= 1e-9:
        return (1.0, 0.0)
    return (dx / L, dy / L)

