import math
import tkinter as tk

class AdvancedCADSnapper:
    """
    Advanced CAD-grade Snapping Engine:
    - Snaps to Endpoints (Vertices) of lines/polygons
    - Snaps to Midpoints of line/polygon segments (draws a green triangle indicator)
    - Snaps to Perpendicular projections from the current start point (draws a blue angle indicator)
    - Integrates seamlessly with GuidelineHelper
    """

    def __init__(self, canvas, model):
        self.canvas = canvas
        self.model = model
        self.snap_distance = 12  # pixels
        self.indicator_ids = []

    def clear_snaps(self):
        """Remove all temporary snap indicators from the canvas."""
        for item_id in self.indicator_ids:
            try:
                self.canvas.delete(item_id)
            except Exception:
                pass
        self.indicator_ids.clear()

    def get_all_canvas_segments(self, exclude_tags=None) -> list[tuple[tuple[float, float], tuple[float, float]]]:
        """
        Gather all active line and polygon segments from the canvas.
        Returns a list of segment tuples: [((x0, y0), (x1, y1)), ...]
        """
        segments = []
        if exclude_tags is None:
            exclude_tags = {"grid", "guideline", "guideline_room", "guideline_grid", "active_text", "vastu_north_marker", "selection_highlight", "screenshot_region", "wall_erase_preview", "multi_erase_highlight", "active_preview"}

        # Find all lines
        for item in self.canvas.find_all():
            try:
                tags = set(self.canvas.gettags(item))
                if any(t in exclude_tags for t in tags):
                    continue
                
                item_type = self.canvas.type(item)
                coords = self.canvas.coords(item)
                
                if not coords or len(coords) < 4:
                    continue

                if item_type == "line":
                    # Single segment
                    segments.append(((float(coords[0]), float(coords[1])), (float(coords[2]), float(coords[3]))))
                
                elif item_type == "polygon":
                    # Loop of segments
                    n = len(coords)
                    points = [(float(coords[i]), float(coords[i+1])) for i in range(0, n - 1, 2)]
                    if len(points) >= 3:
                        for i in range(len(points)):
                            segments.append((points[i], points[(i + 1) % len(points)]))
                
                elif item_type == "rectangle":
                    # 4 segments
                    x0, y0, x1, y1 = map(float, coords[:4])
                    pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
                    for i in range(4):
                        segments.append((pts[i], pts[(i + 1) % 4]))
            except Exception:
                continue

        return segments

    def find_snap_point(self, mouse_x, mouse_y, first_point=None) -> tuple[float, float, dict]:
        """
        Evaluate canvas segments and find the best snapped point.
        Prioritizes: Endpoint -> Midpoint -> Perpendicular -> Orthogonal/Grid (handled by GuidelineHelper fallback).
        """
        self.clear_snaps()
        segments = self.get_all_canvas_segments()
        
        best_x, best_y = mouse_x, mouse_y
        snap_type = "none"
        min_dist = float("inf")
        source_segment = None

        # 1. Check Endpoints (Vertices)
        for seg in segments:
            for pt in seg:
                dist = math.hypot(mouse_x - pt[0], mouse_y - pt[1])
                if dist < self.snap_distance and dist < min_dist:
                    min_dist = dist
                    best_x, best_y = pt
                    snap_type = "endpoint"
                    source_segment = seg

        # 2. Check Midpoints (only if no endpoint snapped)
        if snap_type == "none":
            for seg in segments:
                (x0, y0), (x1, y1) = seg
                mx = (x0 + x1) / 2.0
                my = (y0 + y1) / 2.0
                dist = math.hypot(mouse_x - mx, mouse_y - my)
                if dist < self.snap_distance and dist < min_dist:
                    min_dist = dist
                    best_x, best_y = mx, my
                    snap_type = "midpoint"
                    source_segment = seg

        # 3. Check Perpendicular Snap (if user has set a first point for drawing)
        if snap_type == "none" and first_point is not None:
            fx, fy = first_point
            for seg in segments:
                (bx, by), (cx, cy) = seg
                # Vector BC
                bc_x = cx - bx
                bc_y = cy - by
                seg_len_sq = bc_x*bc_x + bc_y*bc_y
                if seg_len_sq < 1e-9:
                    continue
                
                # Projection of first_point (F) onto segment BC
                t = ((fx - bx) * bc_x + (fy - by) * bc_y) / seg_len_sq
                
                # Clamp to segment bounds to ensure the perpendicular foot is on the segment
                if 0.0 <= t <= 1.0:
                    px = bx + t * bc_x
                    py = by + t * bc_y
                    
                    # Distance from mouse cursor to perpendicular foot
                    dist = math.hypot(mouse_x - px, mouse_y - py)
                    if dist < self.snap_distance and dist < min_dist:
                        min_dist = dist
                        best_x, best_y = px, py
                        snap_type = "perpendicular"
                        source_segment = seg

        snap_info = {
            "snap_type": snap_type,
            "segment": source_segment
        }
        
        # Draw visual indicators
        if snap_type != "none":
            self.draw_snap_indicator(best_x, best_y, snap_type)

        return best_x, best_y, snap_info

    def draw_snap_indicator(self, x, y, snap_type):
        """Draw AutoCAD style geometric snap indicators."""
        r = 6  # radius of indicator
        
        if snap_type == "endpoint":
            # Magenta Square for endpoint
            box_id = self.canvas.create_rectangle(
                x - r, y - r, x + r, y + r,
                outline="#d90429", fill="#ffccd5", width=2,
                tags="active_snap_indicator"
            )
            self.indicator_ids.append(box_id)
            
        elif snap_type == "midpoint":
            # Green Triangle for midpoint
            tri_coords = [x, y - r, x - r, y + r, x + r, y + r]
            tri_id = self.canvas.create_polygon(
                tri_coords,
                outline="#007200", fill="#d8f3dc", width=2,
                tags="active_snap_indicator"
            )
            self.indicator_ids.append(tri_id)
            
        elif snap_type == "perpendicular":
            # Blue Perpendicular Right-Angle Symbol
            # Draws an L-like bracket symbol
            size = 8
            line1 = self.canvas.create_line(x - size, y, x, y, fill="#005f73", width=2, tags="active_snap_indicator")
            line2 = self.canvas.create_line(x, y, x, y - size, fill="#005f73", width=2, tags="active_snap_indicator")
            self.indicator_ids.extend([line1, line2])
