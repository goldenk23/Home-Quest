

import tkinter as tk
import customtkinter as ctk
# from layout_serializer import LayoutSerializer
from canvas_events import CanvasSaveHandler

# def add_serialization_buttons(toolbar_tabs, model, view, tools, actions):
#     """Add serialization buttons to the toolbar."""
#     # Create a serializer
#     serializer = LayoutSerializer(model, view, tools, actions)
    
#     # Add buttons to the Edit tab
#     edit_tab = toolbar_tabs["edit"]
    
#     # Add a separator
#     ctk.CTkLabel(edit_tab, text="").pack(pady=5)
#     ctk.CTkLabel(edit_tab, text="Save/Load Layout", font=("Arial", 12, "bold")).pack(pady=5)
    
#     # Add save/load buttons
#     ctk.CTkButton(edit_tab, text="Save as JSON", command=serializer.save_to_json).pack(pady=4)
#     ctk.CTkButton(edit_tab, text="Load from JSON", command=serializer.load_from_json).pack(pady=4)
#     ctk.CTkButton(edit_tab, text="Save as YAML", command=serializer.save_to_yaml).pack(pady=4)
#     ctk.CTkButton(edit_tab, text="Load from YAML", command=serializer.load_from_yaml).pack(pady=4)
    
#     return serializer




import customtkinter as ctk
from layout_serializer import LayoutSerializer

def add_serialization_buttons(toolbar_tabs, model, view, tools, actions):
    serializer = LayoutSerializer(model, view, tools, actions)
    edit_tab = toolbar_tabs["edit"]
    
    # Add separator and buttons
    ctk.CTkLabel(edit_tab, text="").pack(pady=5)
    ctk.CTkLabel(edit_tab, text="Save/Load Layout", font=("Arial", 12, "bold")).pack(pady=5)
    
    ctk.CTkButton(edit_tab, text="Save as JSON", command=serializer.save_to_json).pack(pady=4)
    ctk.CTkButton(edit_tab, text="Load from JSON", command=serializer.load_from_json).pack(pady=4)
    ctk.CTkButton(edit_tab, text="Save as YAML", command=serializer.save_to_yaml).pack(pady=4)
    ctk.CTkButton(edit_tab, text="Load from YAML", command=serializer.load_from_yaml).pack(pady=4)
    
    return serializer
