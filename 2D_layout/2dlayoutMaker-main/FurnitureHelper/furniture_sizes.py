"""
FurnitureHelper/furniture_sizes.py

Constants file for defining standard furniture sizes in feet (length, width).
All sizes are defined in feet and can be easily modified here.
"""

# Standard furniture sizes in feet (length, width)
STANDARD_FURNITURE_SIZES = {
    # Sofa set with centre table (keep aliases for robustness)
    "tv": (5, 1),                # 5ft x 1ft (TV/Television)
    "Sofa_Set_with_Centre_Table": (9, 6),     # 9ft x 6ft
    "sofa_set_with_centre_table": (9, 6),     # alias (lowercase)
    "double_bed": (6, 6),        # 6ft x 6ft
    "single_bed": (4, 6),      # 6.5ft x 3ft
    "black-box": (2, 2),        # 12ft x 6ft
    "wardrobe": (2, 6),          # 2ft x 6ft
    "desk": (5, 2.5),              # 4ft x 2ft
    "sofa": (6, 3),              # 6ft x 3ft
    "coffee_table": (3, 2),      # 3ft x 2ft
    "fridge": (2.5, 4),        # 2.5ft x 2.5ft
    "bathtub": (5.5, 2.5),       # 5.5ft x 2.5ft    
    "shower": (2, 2),            # 3ft x 3ft
    "toilet": (2, 2),          # 3ft x 3ft
    "sink": (2, 2),            # 2ft x 2ft
    "Wash_basin": (2, 2),      # 2ft x 2ft (alias for sink)
    "wash_basin": (2, 2),      # 2ft x 2ft (alias for sink, lowercase)
    "stove": (3, 3),             # 3ft x 3ft
    "chair": (2, 2),             # 2ft x 2ft
    "dining_table_8_seat": (6, 4),  # 6ft x 4ft
    "dining_table_4_seat": (4, 2),  # 4ft x 2ft
    "dining_table_6_seat": (6, 3),  # 6ft x 3ft
    # Door sizes (approximate width x thickness in feet)
    "singlehand_door": (3, 3),    # ~3ft wide single door
    "doublehand_door": (6, 3),    # ~6ft wide double door
    # Standing cabinet (tall storage)
    "standing_cabinet": (4, 2),     # 4ft x 2ft
    "bed_with_side_table": (8, 6),  # 6ft x 6ft
    "table_chair_set": (6, 4),     # 6ft x 4ft (table with chairs)
    "Table_Chair_Set": (6, 4),     # 6ft x 4ft (alternative name)
    "study_table_chair": (6, 4),     # 6ft x 8ft (study table with chairs)
    "kitchen_platform": (8, 4),     # 8ft x 4ft (kitchen platform)
    "kitchen_platform_2": (9, 7),     # 8ft x 4ft (kitchen platform)
    "kitchen_platform_3": (6, 4),     # 6ft x 4ft (kitchen platform)
    "kitchen_platform_4": (6, 6),     # 6ft x 6ft (kitchen platform)
    "circular_bed":(6, 6),     # 6ft x 6ft (circular bed)
    "single_sofa":(3, 3),     # 6ft x 3ft (single sofa)
    "wardrobe" : (2, 6),            # 2ft x 6ft
}
