# # canvas_events.py

# import tkinter as tk
# from tkinter import messagebox

# class CanvasSaveHandler:
#     def __init__(self, serializer, model):
#         self.serializer = serializer
#         self.model = model
#         self.setup_save_bindings()
    
#     def setup_save_bindings(self):
#         """Set up keyboard shortcuts for saving."""
#         # Bind Ctrl+S to save function
#         self.serializer.canvas.bind_all("<Control-s>", self.handle_save_shortcut)
#         self.serializer.canvas.bind_all("<Control-S>", self.handle_save_shortcut)
    
#     def handle_save_shortcut(self, event=None):
#         """Handle Ctrl+S save shortcut."""
#         self.save_canvas_state()
#         return "break"  # Prevent default behavior
    
#     def save_canvas_state(self):
#         """Save the current canvas state to JSON."""
#         success = self.serializer.save_current_layout(prompt_user=False)
        
#         if success:
#             messagebox.showinfo("Save Successful", 
#                               f"Layout saved to:\n{self.serializer.current_layout_file}")
#         else:
#             # If no current file, prompt for location
#             self.serializer.save_to_json()
    
#     def auto_save_on_change(self):
#         """Trigger auto-save after canvas changes."""
#         if hasattr(self.model, 'canvas_modified') and self.model.canvas_modified:
#             self.serializer.auto_save_layout()
#             self.model.canvas_modified = False




import tkinter as tk
import json  # Add this import

from Helper.showMessage import show_message

class CanvasSaveHandler:
    def __init__(self, serializer, model):
        self.serializer = serializer
        self.model = model
        self.setup_save_bindings()
    
    def setup_save_bindings(self):
        # Fix the empty event strings
        self.serializer.canvas.bind_all("<Control-s>", self.handle_save_shortcut)
        self.serializer.canvas.bind_all("<Control-S>", self.handle_save_shortcut)
    
    def handle_save_shortcut(self, event=None):
        self.save_canvas_state()
        return "break"
    
    def save_canvas_state(self):
        if self.serializer.current_layout_file:
            try:
                layout = self.serializer.serialize_layout()
                with open(self.serializer.current_layout_file, 'w') as f:
                    json.dump(layout, f, indent=2)
                show_message(
                    "info",
                    "VastuCraft Pro",
                    f"Layout updated at:\n{self.serializer.current_layout_file}",
                )
            except Exception as e:
                show_message(
                    "error",
                    "VastuCraft Pro",
                    f"Save failed:\n{e}",
                )
        else:
            self.serializer.save_to_json()