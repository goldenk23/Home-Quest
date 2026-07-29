import tkinter as tk
from tkinter import ttk, filedialog
import json
import math
import sys
import os
from PIL import Image, ImageTk  # Add this line

from Helper.showMessage import show_message


class FloorPlanCanvas:
    def __init__(self, root):
        self.root = root
        self.root.title("Floor Plan Viewer")
        self.root.geometry("1400x900")
        
        # Initialize variables
        self.data = None
        self.canvas_width = 1206
        self.canvas_height = 800
        self.zoom_factor = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.last_x = 0
        self.last_y = 0

        # Initialize image storage to prevent garbage collection
        self.furniture_images = []
        self.flooring_images = []
        
        self.setup_ui()
        
    def setup_ui(self):
        # Create menu bar
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open JSON", command=self.open_file)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Zoom In", command=self.zoom_in)
        view_menu.add_command(label="Zoom Out", command=self.zoom_out)
        view_menu.add_command(label="Reset View", command=self.reset_view)
        
        # Main frame
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Canvas frame with scrollbars
        canvas_frame = ttk.Frame(main_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create canvas with scrollbars
        self.canvas = tk.Canvas(canvas_frame, bg='white', scrollregion=(0, 0, 1500, 1200))
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        h_scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        
        self.canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Grid layout for canvas and scrollbars
        self.canvas.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")
        
        canvas_frame.grid_rowconfigure(0, weight=1)
        canvas_frame.grid_columnconfigure(0, weight=1)
        
        # Bind mouse events
        self.canvas.bind("<Button-1>", self.start_pan)
        self.canvas.bind("<B1-Motion>", self.pan)
        self.canvas.bind("<MouseWheel>", self.mouse_scroll)
        self.canvas.bind("<Shift-MouseWheel>", self.mouse_scroll_horizontal)
        
        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready - Load a JSON file to begin")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
    def open_file(self):
        file_path = filedialog.askopenfilename(
            title="Select JSON file",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if file_path:
            self.load_json(file_path)
    
    def load_json(self, file_path):
        try:
            with open(file_path, 'r') as file:
                self.data = json.load(file)
            
            # Update canvas dimensions from metadata
            metadata = self.data.get('metadata', {})
            self.canvas_width = metadata.get('canvas_width', 1206)
            self.canvas_height = metadata.get('canvas_height', 800)
            
            # Update scrollregion
            self.canvas.configure(scrollregion=(0, 0, self.canvas_width + 200, self.canvas_height + 200))
            
            self.render_floor_plan()
            
            # Update status
            project_name = metadata.get('project_name', 'Floor Plan')
            self.status_var.set(f"Loaded: {project_name} - {os.path.basename(file_path)}")
            
        except Exception as e:
            show_message(
                "error",
                "VastuCraft Pro",
                f"Failed to load JSON file:\n{e}",
            )
    
    def render_floor_plan(self):
        # Clear canvas
        self.canvas.delete("all")
        
        if not self.data:
            return
        
        # Draw grid
        self.draw_grid()
        
        # Draw shapes first (background elements)
        self.draw_shapes()
        
        # Draw rooms
        self.draw_rooms()
        
        # Draw furniture
        self.draw_furniture()
        
        # Draw text elements
        self.draw_text()
    
    def draw_grid(self):
        """Draw background grid"""
        metadata = self.data.get('metadata', {})
        grid_spacing = metadata.get('grid_spacing', 20)
        
        # Vertical lines
        for x in range(0, self.canvas_width + grid_spacing, grid_spacing):
            self.canvas.create_line(x, 0, x, self.canvas_height, fill='#f0f0f0', width=1)
        
        # Horizontal lines
        for y in range(0, self.canvas_height + grid_spacing, grid_spacing):
            self.canvas.create_line(0, y, self.canvas_width, y, fill='#f0f0f0', width=1)
    
    def draw_rooms(self):
        """Draw room elements with flooring support"""
        from PIL import Image, ImageTk
        
        rooms = self.data.get('rooms', [])
        
        for room in rooms:
            x = room.get('x', 0)
            y = room.get('y', 0)
            width = room.get('width', 100)
            height = room.get('height', 100)
            
            fill_color = self.convert_color(room.get('fill_color', '#d0f0c0'))
            outline_color = self.convert_color(room.get('outline_color', 'black'))
            
            # Check if room has flooring
            flooring = room.get('flooring', {})
            if flooring.get('has_flooring', False):
                self.draw_room_with_flooring(x, y, width, height, flooring, outline_color)
            else:
                # Draw regular room without flooring
                self.canvas.create_rectangle(
                    x, y, x + width, y + height,
                    fill=fill_color,
                    outline=outline_color,
                    width=2,
                    tags="room"
                )
         
    def draw_room_with_flooring(self, x, y, width, height, flooring, outline_color):
        """Draw room with flooring image"""
        from PIL import Image, ImageTk
        import os
        
        flooring_path = flooring.get('image_path', '')
        
        # Try to load the flooring image
        if os.path.exists(flooring_path):
            try:
                # Load and resize flooring image to fit room dimensions
                img = Image.open(flooring_path)
                img = img.resize((int(width), int(height)), Image.Resampling.LANCZOS)
                
                # Convert to PhotoImage for tkinter
                self.flooring_image = ImageTk.PhotoImage(img)
                
                # Create flooring image on canvas
                self.canvas.create_image(
                    x, y,
                    image=self.flooring_image,
                    anchor="nw",
                    tags="flooring"
                )
                
                # Add room border
                self.canvas.create_rectangle(
                    x, y, x + width, y + height,
                    outline=outline_color,
                    width=2,
                    fill="",
                    tags="room_border"
                )
                
            except Exception as e:
                print(f"Error loading flooring image: {e}")
                # Fallback to solid color
                self.canvas.create_rectangle(
                    x, y, x + width, y + height,
                    fill="#d0f0c0",
                    outline=outline_color,
                    width=2,
                    tags="room"
                )
        else:
            print(f"Flooring image not found: {flooring_path}")
            # Fallback to solid color
            self.canvas.create_rectangle(
                x, y, x + width, y + height,
                fill="#d0f0c0",
                outline=outline_color,
                width=2,
                tags="room"
            )





    
    def draw_furniture(self):
        """Draw furniture elements"""
        from PIL import Image, ImageTk
        import os

        furniture_list = self.data.get('furniture', [])
    
        for furniture in furniture_list:
            x = furniture.get('x', 0)
            y = furniture.get('y', 0)
            scale = furniture.get('scale', 1.0)
            angle = furniture.get('angle', 0)
            
            image_path = furniture.get('image_path', '')
            
            if os.path.exists(image_path):
                self.draw_furniture_image(x, y, scale, angle, image_path)
            else:
                # Fallback to geometric representation
                self.draw_furniture_fallback(x, y, scale, angle)


         # for furniture in furniture_list:
        #     x = furniture.get('x', 0)
        #     y = furniture.get('y', 0)
        #     scale = furniture.get('scale', 1.0)
        #     angle = furniture.get('angle', 0)
            
        #     # For now, draw furniture as a scaled rectangle with rotation indicator
        #     size = 50 * scale
            
        #     # Calculate rotated rectangle points
        #     points = self.get_rotated_rectangle_points(x, y, size, size * 0.6, angle)
            
        #     # Draw furniture as polygon
        #     self.canvas.create_polygon(
        #         points,
        #         fill='#8B4513',
        #         outline='#654321',
        #         width=2,
        #         tags="furniture"
        #     )
            
        #     # Add rotation indicator line
        #     end_x = x + (size * 0.5) * math.cos(math.radians(angle))
        #     end_y = y + (size * 0.5) * math.sin(math.radians(angle))
            
        #     self.canvas.create_line(
        #         x, y, end_x, end_y,
        #         fill='red',
        #         width=2,
        #         tags="furniture"
        #     )

    def draw_furniture_image(self, x, y, scale, angle, image_path):
        """Draw furniture using actual image with rotation and scaling"""
        from PIL import Image, ImageTk
        import math
        
        try:
            # Load original furniture image
            img = Image.open(image_path)
            
            # Calculate scaled dimensions
            original_width, original_height = img.size
            new_width = int(original_width * scale)
            new_height = int(original_height * scale)
            
            # Resize image
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Rotate image if needed
            if angle != 0:
                img = img.rotate(-angle, expand=True, fillcolor=(255, 255, 255, 0))
            
            # Convert to PhotoImage
            self.furniture_image = ImageTk.PhotoImage(img)
            
            # Create furniture image on canvas
            furniture_id = self.canvas.create_image(
                x, y,
                image=self.furniture_image,
                anchor="center",
                tags="furniture"
            )
            
            # Store reference to prevent garbage collection
            if not hasattr(self, 'furniture_images'):
                self.furniture_images = []
            self.furniture_images.append(self.furniture_image)
            
        except Exception as e:
            print(f"Error loading furniture image: {e}")
            # Fallback to geometric representation
            self.draw_furniture_fallback(x, y, scale, angle)

    def draw_furniture_fallback(self, x, y, scale, angle):
        """Fallback furniture drawing method"""
        size = 50 * scale
        points = self.get_rotated_rectangle_points(x, y, size, size * 0.6, angle)
        
        self.canvas.create_polygon(
            points,
            fill='#8B4513',
            outline='#654321',
            width=2,
            tags="furniture"
        )
        
        # Add rotation indicator
        end_x = x + (size * 0.5) * math.cos(math.radians(angle))
        end_y = y + (size * 0.5) * math.sin(math.radians(angle))
        
        self.canvas.create_line(
            x, y, end_x, end_y,
            fill='red',
            width=2,
            tags="furniture"
        )

        
       
    
    def draw_shapes(self):
        """Draw shape elements"""
        shapes = self.data.get('shapes', [])
        
        for shape in shapes:
            shape_type = shape.get('type', '')
            points = shape.get('points', [])
            
            if not points:
                continue
            
            fill_color = self.convert_color(shape.get('fill_color', ''))
            outline_color = self.convert_color(shape.get('outline_color', 'black'))
            width = shape.get('width', 1.0)
            
            if shape_type == 'rectangle' and len(points) >= 2:
                x1, y1 = points[0]
                x2, y2 = points[1]
                self.canvas.create_rectangle(
                    x1, y1, x2, y2,
                    fill=fill_color if fill_color else '',
                    outline=outline_color,
                    width=int(width),
                    tags="shape"
                )
            
            elif shape_type == 'oval' and len(points) >= 2:
                x1, y1 = points[0]
                x2, y2 = points[1]
                self.canvas.create_oval(
                    x1, y1, x2, y2,
                    fill=fill_color if fill_color else '',
                    outline=outline_color,
                    width=int(width),
                    tags="shape"
                )
            
            elif shape_type == 'line' and len(points) >= 2:
                x1, y1 = points[0]
                x2, y2 = points[1]
                self.canvas.create_line(
                    x1, y1, x2, y2,
                    fill=outline_color,
                    width=int(width),
                    tags="shape"
                )
            
            elif shape_type == 'polygon' and len(points) >= 3:
                # Flatten points for tkinter
                flat_points = []
                for point in points:
                    flat_points.extend(point)
                
                self.canvas.create_polygon(
                    flat_points,
                    fill=fill_color if fill_color else '',
                    outline=outline_color,
                    width=int(width),
                    tags="shape"
                )
    
    def draw_text(self):
        """Draw text elements"""
        text_elements = self.data.get('text', [])
        
        for text_elem in text_elements:
            content = text_elem.get('content', '')
            x = text_elem.get('x', 0)
            y = text_elem.get('y', 0)
            font_info = text_elem.get('font', 'Arial 7')
            color = self.convert_color(text_elem.get('color', 'black'))
            
            # Parse font
            font_parts = font_info.split()
            font_family = font_parts[0] if font_parts else 'Arial'
            font_size = int(font_parts[1]) if len(font_parts) > 1 else 7
            
            # Handle multi-line text
            if '\n' in content:
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    self.canvas.create_text(
                        x, y + (i * (font_size + 2)),
                        text=line,
                        font=(font_family, font_size),
                        fill=color,
                        anchor='nw',
                        tags="text"
                    )
            else:
                self.canvas.create_text(
                    x, y,
                    text=content,
                    font=(font_family, font_size),
                    fill=color,
                    anchor='nw',
                    tags="text"
                )
    
    def get_rotated_rectangle_points(self, cx, cy, width, height, angle_deg):
        """Calculate points for a rotated rectangle"""
        angle_rad = math.radians(angle_deg)
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        
        # Half dimensions
        hw = width / 2
        hh = height / 2
        
        # Corner points relative to center
        corners = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
        
        # Rotate and translate points
        rotated_points = []
        for x, y in corners:
            rx = x * cos_a - y * sin_a + cx
            ry = x * sin_a + y * cos_a + cy
            rotated_points.extend([rx, ry])
        
        return rotated_points
    
    def convert_color(self, color_str):
        """Convert color string to tkinter-compatible color"""
        if not color_str or color_str == '':
            return ''
        
        # Handle system colors
        color_mapping = {
            'systemTextColor': 'black',
            'systemBackgroundColor': 'white'
        }
        
        return color_mapping.get(color_str, color_str)
    
    def start_pan(self, event):
        """Start panning operation"""
        self.last_x = event.x
        self.last_y = event.y
    
    def pan(self, event):
        """Pan the canvas"""
        dx = event.x - self.last_x
        dy = event.y - self.last_y
        
        self.canvas.scan_dragto(-dx, -dy, gain=1)
        
        self.last_x = event.x
        self.last_y = event.y
    
    def mouse_scroll(self, event):
        """Handle vertical mouse scroll"""
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
    
    def mouse_scroll_horizontal(self, event):
        """Handle horizontal mouse scroll"""
        self.canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")
    
    def zoom_in(self):
        """Zoom in function"""
        self.zoom_factor *= 1.2
        self.apply_zoom()
    
    def zoom_out(self):
        """Zoom out function"""
        self.zoom_factor /= 1.2
        self.apply_zoom()
    
    def reset_view(self):
        """Reset view to original"""
        self.zoom_factor = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)
        self.render_floor_plan()
    
    def apply_zoom(self):
        """Apply zoom transformation"""
        # This is a simplified zoom - in a full implementation,
        # you'd scale all coordinates
        self.render_floor_plan()

def main():
    root = tk.Tk()
    app = FloorPlanCanvas(root)
    
    # If JSON file provided as argument, load it
    if len(sys.argv) > 1:
        json_file = sys.argv[1]
        if os.path.exists(json_file):
            app.load_json(json_file)
    
    root.mainloop()

if __name__ == "__main__":
    main()
