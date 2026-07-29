import math
import tkinter as tk
from entities import RoomEntity
from Helper.showMessage import show_message

class VastuLayoutGenerator:
    """
    Next-Generation AI Vastu Floor Plan Engine:
    Algorithmic room distribution packer and auto-furnishing engine
    that partitions a plot boundary according to classical Vastu Shastra rules
    and places furniture items in Vastu-compliant positions and angles.
    """

    def __init__(self, tools, model, view, actions):
        self.tools = tools
        self.model = model
        self.view = view
        self.canvas = view.canvas
        self.actions = actions

    def _real_to_px(self, value: float) -> float:
        unit = getattr(self.model, "unit", "m")
        unit_scale = getattr(self.model, "unit_scale", {}) or {}
        scale = float(unit_scale.get(unit, 1.0))
        grid = float(getattr(self.model, "grid_spacing", 20))
        zoom = float(getattr(self.model, "zoom_level", 1.0))
        return (float(value) / scale) * grid * zoom

    def generate_vastu_bhk_layout(self, length: float, breadth: float, bhk_type: str, facing_direction: str, selected_furniture: dict, show_dims: bool = True) -> bool:
        """
        Auto-generate a complete, fully-furnished Vastu-compliant BHK layout.
        
        Args:
            length: Plot length (vertical) in active units
            breadth: Plot width (horizontal) in active units
            bhk_type: "1 BHK" | "2 BHK" | "3 BHK" | "4 BHK"
            facing_direction: "East" | "North" | "West" | "South"
            selected_furniture: Dict of boolean checkboxes: {'bed': True, 'sofa': True, etc.}
            show_dims: Boolean toggle to draw outer plot measurements
        """
        if length <= 0 or breadth <= 0:
            show_message("error", "Vastu AI Planner", "Plot dimensions must be greater than 0.")
            return False

        # Clear canvas safely to draft clean floor plans
        try:
            self.tools.reset_all_canvas(confirm=False)
        except Exception:
            pass

        unit = getattr(self.model, "unit", "m")
        unit_factor = self.model.unit_scale[unit]
        pixels_per_unit = (self.model.grid_spacing * self.model.zoom_level) / unit_factor

        # 1. Calculate Viewport Center in Canvas Space
        w = float(self.canvas.winfo_width() or 0)
        h = float(self.canvas.winfo_height() or 0)
        if w < 10 or h < 10:
            w, h = 1200, 800  # Fallback

        cx = float(self.canvas.canvasx(w / 2.0))
        cy = float(self.canvas.canvasy(h / 2.0))

        # Auto-Zoom logic to fit plot nicely in view
        try:
            base_w_px = length * pixels_per_unit / self.model.zoom_level
            base_h_px = breadth * pixels_per_unit / self.model.zoom_level
            if base_w_px > 0 and base_h_px > 0:
                ideal_zoom = min((w * 0.70) / base_w_px, (h * 0.70) / base_h_px)
                ideal_zoom = max(0.005, min(ideal_zoom, 1.0))
                scale_factor = ideal_zoom / self.model.zoom_level
                if abs(scale_factor - 1.0) > 1e-4:
                    self.view.apply_zoom(scale_factor)
                    pixels_per_unit = (self.model.grid_spacing * self.model.zoom_level) / unit_factor
        except Exception as e:
            print(f"[Vastu Auto-Zoom] Failed: {e}")

        # Recalculate plot size in pixels
        w_px = length * pixels_per_unit
        h_px = breadth * pixels_per_unit
        
        plot_x0 = cx - (w_px / 2.0)
        plot_y0 = cy - (h_px / 2.0)

        # Ensure any old Vastu polygon visual groups, rooms and furniture are fully removed from canvas
        for tag in ("vastu_polygon", "vastu_polygon_temp", "vastu_group", "room", "furniture", "vastu_dimensions"):
            try:
                self.canvas.delete(tag)
            except Exception:
                pass

        # 2. Draw Plot Outer Boundary using the authentic Vastu Polygon drawing engine natively!
        plot_x1 = plot_x0 + w_px
        plot_y1 = plot_y0 + h_px
        
        poly_points = [
            (plot_x0, plot_y0),
            (plot_x1, plot_y0),
            (plot_x1, plot_y1),
            (plot_x0, plot_y1)
        ]
        
        # Register points in the native Vastu Polygon system for CAD integration
        self.tools.vastu_polygon_points = list(poly_points)
        
        # Determine the target Vastu North orientation angle
        facing_to_north_deg = {
            "East": 270.0,
            "North": 0.0,
            "West": 90.0,
            "South": 180.0
        }
        target_deg = facing_to_north_deg.get(facing_direction, 0.0)
        self.tools.vastu_north_deg = target_deg
        
        # Configure layout dimensions toggle in the model state
        setattr(self.model, "auto_vastu_polygon_dimensions", show_dims)
        
        # Capture user's preferred draw type and temporarily force "normal" (outline only)
        # to prevent cluttered division lines/sections from cutting through the generated room plan.
        orig_draw_type = str(self.model.get("vastu_polygon_draw_type"))
        self.model.set("vastu_polygon_draw_type", "normal")
        
        # We temporarily mock the Vastu north dialog, the marker arrow, and the logger so the popup is completely bypassed
        orig_ask_fn = self.tools._ask_vastu_north_deg
        orig_log_fn = self.actions.log
        orig_marker_fn = self.tools._draw_vastu_north_marker
        captured_vastu_action = None
        
        def mock_log(action):
            nonlocal captured_vastu_action
            captured_vastu_action = action
            
        try:
            self.tools._ask_vastu_north_deg = lambda default_deg=0.0: target_deg
            self.actions.log = mock_log
            self.tools._draw_vastu_north_marker = lambda *args, **kwargs: None
            
            # Call authentic Vastu Polygon engine natively!
            self.tools.finish_vastu_polygon()
        finally:
            self.tools._ask_vastu_north_deg = orig_ask_fn
            self.actions.log = orig_log_fn
            self.tools._draw_vastu_north_marker = orig_marker_fn
            # Restore the user's original preferred Vastu draw type
            self.model.set("vastu_polygon_draw_type", orig_draw_type)
            
        outer_boundary_items = []
        if captured_vastu_action:
            outer_boundary_items = list(captured_vastu_action.get("items", []))
        else:
            try:
                outer_boundary_items = list(self.canvas.find_withtag("vastu_group"))
            except Exception:
                pass
                
        # Draw native area & perimeter label inside the polygon for premium UX
        try:
            from geometry import calculate_polygon_area, calculate_polygon_perimeter
            unit = getattr(self.model, "unit", "m")
            zoom_level = float(getattr(self.model, "zoom_level", 1.0))
            area = calculate_polygon_area(poly_points, unit, zoom_level)
            perimeter = calculate_polygon_perimeter(poly_points, unit, zoom_level)
            
            serial = int(getattr(self.tools, "_polygon_label_serial", 0) or 0) + 1
            setattr(self.tools, "_polygon_label_serial", serial)
            
            label_text = f"Plot Area: {area:.2f} {unit}²\nPerimeter: {perimeter:.2f} {unit}"
            label_id = self.tools.polygon_label_placer.create_polygon_label(
                poly_points,
                label_text,
                tags=("polygon_label", "vastu_group"),
                fill="black",
                font=("Arial", 10),
            )
            self.canvas.tag_raise(label_id)
            # Shift the plot area and perimeter label slightly downwards to prevent overlap with room label
            try:
                self.canvas.move(label_id, 0, self._real_to_px(2.5))
            except Exception:
                pass
            outer_boundary_items.append(label_id)
        except Exception as e:
            print(f"[Vastu Generator] Failed to create native polygon label: {e}")

        # 3. Dynamic Room Allocation Matrix (Realistic Proportional Geometries, 100% Filled)
        x_m1 = plot_x0 + 0.35 * w_px
        x_m2 = plot_x0 + 0.55 * w_px
        x_m3 = plot_x0 + 0.70 * w_px
        
        y_m1 = plot_y0 + 0.28 * h_px
        y_m2 = plot_y0 + 0.65 * h_px

        rooms_config = []
        if bhk_type == "1 BHK":
            rooms_config = [
                # Name, x0, y0, x1, y1
                ("Master Bedroom", plot_x0, y_m2, x_m3, plot_y1),
                ("Vastu Kitchen", x_m3, y_m2, plot_x1, plot_y1),
                ("Living & Dining Lounge", plot_x0, y_m1, plot_x1, y_m2),
                ("Common Washroom", plot_x0, plot_y0, x_m1, y_m1),
                ("Entrance Lobby & Pooja", x_m1, plot_y0, plot_x1, y_m1)
            ]
        elif bhk_type == "2 BHK":
            rooms_config = [
                ("Master Bedroom", plot_x0, y_m2, x_m1, plot_y1),
                ("Attached Toilet", x_m1, y_m2, x_m3, plot_y1),
                ("Vastu Kitchen", x_m3, y_m2, plot_x1, plot_y1),
                ("Living & Dining Lounge", plot_x0, y_m1, plot_x1, y_m2),
                ("Guest Bedroom", plot_x0, plot_y0, x_m1, y_m1),
                ("Common Washroom", x_m1, plot_y0, x_m3, y_m1),
                ("Pooja Room", x_m3, plot_y0, plot_x1, y_m1)
            ]
        elif bhk_type == "3 BHK":
            rooms_config = [
                ("Master Bedroom", plot_x0, y_m2, x_m1, plot_y1),
                ("Attached Toilet", x_m1, y_m2, x_m3, plot_y1),
                ("Vastu Kitchen", x_m3, y_m2, plot_x1, plot_y1),
                ("Kids Bedroom", plot_x0, y_m1, x_m1, y_m2),
                ("Living & Dining Lounge", x_m1, y_m1, plot_x1, y_m2),
                ("Guest Bedroom", plot_x0, plot_y0, x_m1, y_m1),
                ("Common Washroom", x_m1, plot_y0, x_m3, y_m1),
                ("Pooja Room", x_m3, plot_y0, plot_x1, y_m1)
            ]
        else:  # 4 BHK
            rooms_config = [
                ("Master Bedroom", plot_x0, y_m2, x_m1, plot_y1),
                ("Attached Toilet", x_m1, y_m2, x_m3, plot_y1),
                ("Vastu Kitchen", x_m3, y_m2, plot_x1, plot_y1),
                ("Kids Bedroom", plot_x0, y_m1, x_m1, y_m2),
                ("Living Room / Lounge", x_m1, y_m1, x_m3, y_m2),
                ("Common Washroom", x_m3, y_m1, plot_x1, y_m2),
                ("Guest Bedroom", plot_x0, plot_y0, x_m1, y_m1),
                ("Study Room", x_m1, plot_y0, x_m3, y_m1),
                ("Pooja Room", x_m3, plot_y0, plot_x1, y_m1)
            ]

        created_rooms = []
        all_room_items = []
        
        # 4. Generate and Align Room Entities
        for name, rx0, ry0, rx1, ry1 in rooms_config:
            # Convert pixel coordinates to real feet/meters size for RoomEntity label
            r_width = (rx1 - rx0) / pixels_per_unit
            r_height = (ry1 - ry0) / pixels_per_unit

            grp_id = getattr(self.model, "room_counter", 0)
            setattr(self.model, "room_counter", grp_id + 1)

            room = RoomEntity(
                self.canvas,
                self.model,
                name,
                r_width,
                r_height,
                grp_id,
                fill_mode="walls_only",
                wall_thickness_ft=0.4
            )
            
            # Place physical room exactly snapped to targeted pixel boundaries
            dx = rx0 - room.x0
            dy = ry0 - room.y0
            self.canvas.move(room.group_tag, dx, dy)
            room.sync_to_canvas()

            self.tools.room_entities_by_group_tag[room.group_tag] = room
            created_rooms.append((name, room, r_width, r_height))
            all_room_items.extend(room.items)

        # 5. Auto-Placement of Vastu Furniture & Premium Internal Decor
        placed_furniture = []
        for name, room, r_w, r_h in created_rooms:
            rx0, ry0, rx1, ry1 = room.x0, room.y0, room.x1, room.y1
            room_bbox = (rx0, ry0, rx1, ry1)
            
            # --- Master Bedroom Bed & Wardrobe Placement ---
            if "Master Bedroom" in name and selected_furniture.get("bed", True):
                # Place bed near SW corner (bottom-left), headboard facing South, perfectly centered and snug!
                x_bed = rx0 + (rx1 - rx0) * 0.5
                y_bed = ry1 - self._real_to_px(3.0)
                item = self.tools.insert_furniture_scaled("double_bed", x_bed, y_bed, room_bbox, r_w, r_h)
                if item:
                    item.angle = 180  # Orient facing South
                    item.update_image()
                    self.canvas.itemconfig(item.image_id, image=item.tk_image)
                    placed_furniture.append(item.image_id)
                    self.tools.commit_furniture_to_underlying_group(item)
                
                # Snug Wardrobe along the West Wall (facing East) - set vertical to hug wall perfectly!
                x_ward = rx0 + self._real_to_px(1.0)
                y_ward = ry0 + (ry1 - ry0) * 0.45
                ward_item = self.tools.insert_furniture_scaled("Wardrobe", x_ward, y_ward, room_bbox, r_w, r_h)
                if ward_item:
                    ward_item.angle = 0  # Vertical snug orientation
                    ward_item.update_image()
                    self.canvas.itemconfig(ward_item.image_id, image=ward_item.tk_image)
                    placed_furniture.append(ward_item.image_id)
                    self.tools.commit_furniture_to_underlying_group(ward_item)

            # --- Kids / Guest Bedroom Bed & Wardrobe Placement ---
            elif ("Kids" in name or "Guest" in name) and selected_furniture.get("bed", True):
                # Place near West wall, headboard facing South - perfectly snug!
                x_bed = rx0 + self._real_to_px(2.0)
                y_bed = ry1 - self._real_to_px(3.0)
                item = self.tools.insert_furniture_scaled("single_bed", x_bed, y_bed, room_bbox, r_w, r_h)
                if item:
                    item.angle = 180  # Orient facing South
                    item.update_image()
                    self.canvas.itemconfig(item.image_id, image=item.tk_image)
                    placed_furniture.append(item.image_id)
                    self.tools.commit_furniture_to_underlying_group(item)
                
                # Wardrobe along the East wall (facing West) - set vertical to hug wall perfectly!
                x_ward = rx1 - self._real_to_px(1.0)
                y_ward = ry0 + self._real_to_px(3.5)
                ward_item = self.tools.insert_furniture_scaled("Wardrobe", x_ward, y_ward, room_bbox, r_w, r_h)
                if ward_item:
                    ward_item.angle = 0  # Vertical snug orientation
                    ward_item.update_image()
                    self.canvas.itemconfig(ward_item.image_id, image=ward_item.tk_image)
                    placed_furniture.append(ward_item.image_id)
                    self.tools.commit_furniture_to_underlying_group(ward_item)

            # --- Kitchen Platform, Stove, Fridge, and Sink Placement ---
            elif "Kitchen" in name:
                # Place a beautiful, large kitchen platform running along the East wall of the kitchen
                x_plat = rx1 - self._real_to_px(2.0)
                y_plat = ry0 + (ry1 - ry0) * 0.5
                plat_item = self.tools.insert_furniture_scaled("kitchen_platform", x_plat, y_plat, room_bbox, r_w, r_h)
                if plat_item:
                    plat_item.angle = 90  # Rotate platform vertically to align with the East wall
                    plat_item.update_image()
                    self.canvas.itemconfig(plat_item.image_id, image=plat_item.tk_image)
                    placed_furniture.append(plat_item.image_id)
                    self.tools.commit_furniture_to_underlying_group(plat_item)

                if selected_furniture.get("stove", True):
                    # Stove on the East kitchen platform in the South-East corner (perfect Vastu)
                    x_stove = rx1 - self._real_to_px(2.0)
                    y_stove = ry1 - self._real_to_px(2.5)
                    item = self.tools.insert_furniture_scaled("stove", x_stove, y_stove, room_bbox, r_w, r_h)
                    if item:
                        item.angle = 90  # Orient facing East
                        item.update_image()
                        self.canvas.itemconfig(item.image_id, image=item.tk_image)
                        placed_furniture.append(item.image_id)
                        self.tools.commit_furniture_to_underlying_group(item)
                    
                    # Sink on the East kitchen platform (perfect Vastu, shifted to avoid door front)
                    x_sink = rx1 - self._real_to_px(2.0)
                    y_sink = ry0 + self._real_to_px(4.0)
                    sink_item = self.tools.insert_furniture_scaled("sink", x_sink, y_sink, room_bbox, r_w, r_h)
                    if sink_item:
                        sink_item.angle = 90  # Orient facing East
                        sink_item.update_image()
                        self.canvas.itemconfig(sink_item.image_id, image=sink_item.tk_image)
                        placed_furniture.append(sink_item.image_id)
                        self.tools.commit_furniture_to_underlying_group(sink_item)
                
                if selected_furniture.get("fridge", True):
                    # Fridge in NW (top-left of Kitchen)
                    x_fridge = rx0 + self._real_to_px(2.0)
                    y_fridge = ry0 + self._real_to_px(2.5)
                    item = self.tools.insert_furniture_scaled("fridge", x_fridge, y_fridge, room_bbox, r_w, r_h)
                    if item:
                        placed_furniture.append(item.image_id)
                        self.tools.commit_furniture_to_underlying_group(item)

            # --- Living Lounge Sofa, TV, and Dining Placement ---
            elif "Living" in name:
                # Dynamic layout swapper based on facing direction to prevent blocking the entrance
                is_west = (facing_direction == "West")
                
                # Center sofa and TV vertically for perfect architect-style alignment
                y_sofa_tv = (ry0 + ry1) / 2
                
                if selected_furniture.get("sofa", True):
                    # Position sofa set dynamically to avoid blocking bedroom doors and entrance
                    if is_west:
                        # West entrance is on the left; place sofa on the right side
                        x_sofa = rx1 - self._real_to_px(r_w * 0.35)
                    else:
                        # Otherwise place sofa on the left side, shifted clear of bedroom doors
                        x_sofa = rx0 + self._real_to_px(r_w * 0.35)
                    
                    item = self.tools.insert_furniture_scaled("Sofa_Set_with_Centre_Table", x_sofa, y_sofa_tv, room_bbox, r_w, r_h)
                    if item:
                        placed_furniture.append(item.image_id)
                        self.tools.commit_furniture_to_underlying_group(item)
                
                if selected_furniture.get("tv", True):
                    # Mount TV exactly opposite to the sofa at the same height
                    if is_west:
                        x_tv = rx0 + self._real_to_px(0.8)
                        tv_angle = 270  # Face right
                    else:
                        x_tv = rx1 - self._real_to_px(0.8)
                        tv_angle = 90   # Face left
                        
                    item = self.tools.insert_furniture_scaled("tv", x_tv, y_sofa_tv, room_bbox, r_w, r_h)
                    if item:
                        item.angle = tv_angle
                        item.update_image()
                        self.canvas.itemconfig(item.image_id, image=item.tk_image)
                        placed_furniture.append(item.image_id)
                        self.tools.commit_furniture_to_underlying_group(item)

                if selected_furniture.get("dining", True):
                    # Upgrade dining table to luxurious "dining_table_6_seat" (6ft x 3ft)
                    # and place it snugly in the upper half of the lounge opposite to the sofa
                    if is_west:
                        x_din = rx0 + self._real_to_px(4.0)
                    else:
                        x_din = rx1 - self._real_to_px(4.0)
                        
                    y_din = ry0 + self._real_to_px(3.5)
                    item = self.tools.insert_furniture_scaled("dining_table_6_seat", x_din, y_din, room_bbox, r_w, r_h)
                    if item:
                        item.angle = 90  # Rotate vertically to sit snug
                        item.update_image()
                        self.canvas.itemconfig(item.image_id, image=item.tk_image)
                        placed_furniture.append(item.image_id)
                        self.tools.commit_furniture_to_underlying_group(item)

            # --- Washroom Toilet, Wash Basin, and Bathtub Placement ---
            elif "Washroom" in name or "Toilet" in name:
                if selected_furniture.get("toilet", True):
                    # Toilet on South wall, facing North - shifted right to completely clear the door swing
                    x_toilet = rx1 - self._real_to_px(3.0)
                    y_toilet = ry1 - self._real_to_px(1.6)
                    item = self.tools.insert_furniture_scaled("Toilet", x_toilet, y_toilet, room_bbox, r_w, r_h)
                    if item:
                        item.angle = 0  # 0 degree to keep the tank flush against the South wall
                        item.update_image()
                        self.canvas.itemconfig(item.image_id, image=item.tk_image)
                        placed_furniture.append(item.image_id)
                        self.tools.commit_furniture_to_underlying_group(item)
                    
                    # Wash Basin on East wall (facing West) - perfectly snug and clear of door swing
                    x_basin = rx1 - self._real_to_px(1.5)
                    y_basin = ry0 + self._real_to_px(1.8)
                    basin_item = self.tools.insert_furniture_scaled("Wash_Basin", x_basin, y_basin, room_bbox, r_w, r_h)
                    if basin_item:
                        basin_item.angle = 270
                        basin_item.update_image()
                        self.canvas.itemconfig(basin_item.image_id, image=basin_item.tk_image)
                        placed_furniture.append(basin_item.image_id)
                        self.tools.commit_furniture_to_underlying_group(basin_item)

                    # Add a luxurious bathtub in the top-left corner of the spacious washroom
                    x_tub = rx0 + self._real_to_px(3.0)
                    y_tub = ry0 + self._real_to_px(1.5)
                    tub_item = self.tools.insert_furniture_scaled("bathtub", x_tub, y_tub, room_bbox, r_w, r_h)
                    if tub_item:
                        tub_item.angle = 0  # Horizontal alignment
                        tub_item.update_image()
                        self.canvas.itemconfig(tub_item.image_id, image=tub_item.tk_image)
                        placed_furniture.append(tub_item.image_id)
                        self.tools.commit_furniture_to_underlying_group(tub_item)

            # --- Pooja Room Cabinet/Altar Placement ---
            elif "Pooja" in name:
                if selected_furniture.get("pooja", True):
                    # Altar on East wall, facing West - perfectly snug!
                    x_pooja = rx1 - self._real_to_px(1.0)
                    y_pooja = (ry0 + ry1) / 2
                    item = self.tools.insert_furniture_scaled("standing_cabinet", x_pooja, y_pooja, room_bbox, r_w, r_h)
                    if item:
                        item.angle = 270
                        item.update_image()
                        self.canvas.itemconfig(item.image_id, image=item.tk_image)
                        placed_furniture.append(item.image_id)
                        self.tools.commit_furniture_to_underlying_group(item)

            # --- Study Room Table & Chair Placement ---
            elif "Study Room" in name:
                # Place premium study table and chair in the middle
                x_study = (rx0 + rx1) / 2
                y_study = (ry0 + ry1) / 2
                item = self.tools.insert_furniture_scaled("Study_Table_Chair", x_study, y_study, room_bbox, r_w, r_h)
                if item:
                    placed_furniture.append(item.image_id)
                    self.tools.commit_furniture_to_underlying_group(item)

        # 5b. Place grand main entrance door on the plot boundary wall (snapped to avoid bedroom/bathroom)
        ent_x, ent_y = cx, cy
        ent_angle = 0
        
        if facing_direction == "East":
            # East wall -> Lead into Dining Area (middle row, right side)
            ent_x = plot_x1
            ent_y = (y_m1 + y_m2) / 2
            ent_angle = 90
        elif facing_direction == "North":
            # North wall -> Lead into Lobby / Foyer (top row, middle side)
            ent_x = (x_m1 + x_m3) / 2
            ent_y = plot_y0
            ent_angle = 180
        elif facing_direction == "West":
            # West wall -> Lead into Passage / Lobby (middle row, left side)
            ent_x = plot_x0
            ent_y = (y_m1 + y_m2) / 2
            ent_angle = 270
        else: # South
            # South wall -> Lead into Balcony / Lobby (bottom row, middle side)
            ent_x = (x_m1 + x_m3) / 2
            ent_y = plot_y1
            ent_angle = 0

        main_door_bbox = (plot_x0, plot_y0, plot_x1, plot_y1)
        main_door_item = self.tools.insert_furniture_scaled(
            "doublehand_door",
            ent_x,
            ent_y,
            main_door_bbox,
            length,
            breadth
        )
        if main_door_item:
            main_door_item.angle = ent_angle
            main_door_item.update_image()
            self.canvas.itemconfig(main_door_item.image_id, image=main_door_item.tk_image)
            setattr(main_door_item, "is_door", True)
            placed_furniture.append(main_door_item.image_id)
            self.tools.commit_furniture_to_underlying_group(main_door_item)

        # 5c. Map and Place internal room doors connecting logically (Refined & Highly Optimized Template Engine)
        room_by_name = {}
        for r_name, room_obj, r_w, r_h in created_rooms:
            room_by_name[r_name] = {
                "obj": room_obj,
                "w_ft": r_w,
                "h_ft": r_h,
                "x0": room_obj.x0,
                "y0": room_obj.y0,
                "x1": room_obj.x1,
                "y1": room_obj.y1,
                "bbox": (room_obj.x0, room_obj.y0, room_obj.x1, room_obj.y1)
            }

        # Compact template mapping: (room_name, wall_side, offset_percentage, rotation_angle)
        door_templates = {
            "1 BHK": [
                ("Master Bedroom", "top", 0.5, 0),
                ("Vastu Kitchen", "top", 0.25, 0),
                ("Common Washroom", "bottom", 0.5, 0),
            ],
            "2 BHK": [
                ("Master Bedroom", "top", 0.5, 0),
                ("Attached Toilet", "left", 0.5, 90),
                ("Vastu Kitchen", "top", 0.25, 0),
                ("Guest Bedroom", "bottom", 0.5, 0),
                ("Common Washroom", "bottom", 0.5, 0),
                ("Pooja Room", "bottom", 0.5, 0),
            ],
            "3 BHK": [
                ("Master Bedroom", "top", 0.5, 0),
                ("Attached Toilet", "left", 0.5, 90),
                ("Vastu Kitchen", "top", 0.25, 0),
                ("Kids Bedroom", "right", 0.5, 90),
                ("Guest Bedroom", "bottom", 0.5, 0),
                ("Common Washroom", "bottom", 0.5, 0),
                ("Pooja Room", "bottom", 0.5, 0),
            ],
            "4 BHK": [
                ("Master Bedroom", "top", 0.5, 0),
                ("Attached Toilet", "left", 0.5, 90),
                ("Vastu Kitchen", "top", 0.25, 0),
                ("Kids Bedroom", "right", 0.5, 90),
                ("Guest Bedroom", "bottom", 0.5, 0),
                ("Study Room", "bottom", 0.5, 0),
                ("Common Washroom", "left", 0.5, 90),
                ("Pooja Room", "bottom", 0.5, 0),
            ]
        }

        for room_name, side, offset, angle in door_templates.get(bhk_type, []):
            if room_name in room_by_name:
                r = room_by_name[room_name]
                rx0, ry0, rx1, ry1 = r["x0"], r["y0"], r["x1"], r["y1"]
                
                # Snapping logic: project coordinates mathematically onto room perimeter walls
                if side == "top":
                    dx = rx0 + (rx1 - rx0) * offset
                    dy = ry0
                elif side == "bottom":
                    dx = rx0 + (rx1 - rx0) * offset
                    dy = ry1
                elif side == "left":
                    dx = rx0
                    dy = ry0 + (ry1 - ry0) * offset
                else:  # right
                    dx = rx1
                    dy = ry0 + (ry1 - ry0) * offset
                
                door_item = self.tools.insert_furniture_scaled(
                    "singlehand_door", dx, dy, r["bbox"], r["w_ft"], r["h_ft"]
                )
                if door_item:
                    door_item.angle = angle
                    door_item.update_image()
                    self.canvas.itemconfig(door_item.image_id, image=door_item.tk_image)
                    setattr(door_item, "is_door", True)
                    placed_furniture.append(door_item.image_id)
                    self.tools.commit_furniture_to_underlying_group(door_item)

        # 6. Compass Direction
        try:
            self.tools.draw_compass(facing_direction[:1])
        except Exception:
            pass

        # 7. Log Action Payload as a clean "create" action for flawless undo/redo support
        all_items = outer_boundary_items + all_room_items + placed_furniture
        self.actions.log({
            "type": "create",
            "items": all_items,
            "dimension_recompute": {
                "group_tag": "vastu_group",
                "dim_tag": "vastu_dimensions",
            }
        })

        # Explicitly raise all doors and furniture to the top of the canvas so they are never covered by walls or room fills!
        try:
            for item_id in self.canvas.find_withtag("furniture"):
                self.canvas.tag_raise(item_id)
            for item_id in self.canvas.find_withtag("furniture_committed"):
                self.canvas.tag_raise(item_id)
        except Exception as e:
            print(f"[Vastu Generator] Failed to raise furniture items: {e}")

        try:
            self.tools.schedule_recompute_door_cuts(delay_ms=10)
        except Exception as e:
            print(f"[Vastu Generator] schedule_recompute_door_cuts failed: {e}")

        self.canvas.update_idletasks()
        show_message("info", "Vastu Floor Plan Generator", f"Success! Generated a Vastu-compliant {bhk_type} layout.")
        return True
