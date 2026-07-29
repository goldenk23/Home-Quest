"""
Furniture Selection Dialog
Modern popup window with furniture cards showing images, sizes, and selection options.

Uses ttkbootstrap (ttkb) for a modern look; falls back to standard ttk if ttkbootstrap
is not available.
"""

import tkinter as tk
from PIL import Image, ImageTk
from Helper.set_window_icon import set_window_icon
try:
    import ttkbootstrap as ttkb
except ImportError:  # Fallback to standard ttk
    import tkinter.ttk as ttkb

from Furniture import find_image_path
import importlib
import sys

# Import furniture_sizes module at module level for proper reloading
try:
    from FurnitureHelper import furniture_sizes
except ImportError:
    furniture_sizes = None


def _norm_key(s: str) -> str:
    """
    Normalize furniture keys so lookups are robust:
    - lowercased
    - strip leading/trailing whitespace
    - remove spaces, underscores and hyphens
    """
    if not s:
        return ""
    s = s.strip().lower()
    for ch in (" ", "_", "-"):
        s = s.replace(ch, "")
    return s


def _get_furniture_sizes():
    """Get latest STANDARD_FURNITURE_SIZES by reloading the module."""
    try:
        # Reload the module to get latest values
        if furniture_sizes is not None:
            importlib.reload(furniture_sizes)
            return furniture_sizes.STANDARD_FURNITURE_SIZES
        else:
            # Fallback: try importing fresh
            from FurnitureHelper import furniture_sizes as fs
            importlib.reload(fs)
            return fs.STANDARD_FURNITURE_SIZES
    except Exception as e:
        # Fallback to direct import if reload fails
        try:
            from FurnitureHelper import STANDARD_FURNITURE_SIZES
            return STANDARD_FURNITURE_SIZES
        except ImportError:
            print(f"Warning: Could not load furniture sizes: {e}")
            return {}


def _get_normalized_sizes():
    """Get latest normalized furniture sizes map."""
    sizes = _get_furniture_sizes()
    return {
        _norm_key(name): size for name, size in sizes.items()
    }


class FurnitureSelectionDialog:
    """Modern furniture selection dialog with card-based UI (ttkb-based)."""

    def __init__(self, parent, category, items, select_callback):
        """
        Initialize the furniture selection dialog.

        Args:
            parent: Parent window
            category: Category name (e.g., "Kitchen", "Beds")
            items: List of furniture item names
            select_callback: Callback function when furniture is selected
        """
        self.parent = parent
        self.category = category
        self.items = items
        self.select_callback = select_callback
        self.selected_item = None
        self.cards = []
        self._selected_card = None
        self._all_items = list(items)
        self._search_var = tk.StringVar(value="")
        
        # Debug: print items received
        print(f"[DEBUG] FurnitureSelectionDialog init - category: '{category}', items: {items}")
        if "tv" in [i.lower() for i in items]:
            print(f"[DEBUG] ✓ 'tv' FOUND in items list")
        else:
            print(f"[DEBUG] ✗ 'tv' NOT found in items list")

        # Create dialog window (standard Tk Toplevel so it works with ttkbootstrap)
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Select {category} Furniture")
        self.dialog.geometry("800x600")
        self.dialog.transient(parent)
        set_window_icon(self.dialog)
        self.dialog.grab_set()

        # Center the window
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (800 // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (600 // 2)
        self.dialog.geometry(f"800x600+{x}+{y}")

        # Style / theme (do not change global app theme; just use styles below)
        self.style = ttkb.Style()

        # Style for cards
        # Base card style
        self.style.configure(
            "Card.TFrame",
            padding=10,
            relief="ridge",
            borderwidth=1
        )
        # Selected card style
        self.style.configure(
            "CardSelected.TFrame",
            padding=10,
            relief="solid",
            borderwidth=2
        )
        # Hover card style
        self.style.configure(
            "CardHover.TFrame",
            padding=10,
            relief="solid",
            borderwidth=1
        )

        # Main container
        main_frame = ttkb.Frame(self.dialog, padding=10)
        main_frame.pack(fill="both", expand=True)

        # Header
        header_frame = ttkb.Frame(main_frame)
        header_frame.pack(fill="x", pady=(0, 10))

        top_row = ttkb.Frame(header_frame)
        top_row.pack(fill="x", pady=(10, 4))

        title_label = ttkb.Label(
            top_row,
            text=f"{category} Furniture",
            font=("Arial", 20, "bold")
        )
        title_label.pack(side="left")

        search_box = ttkb.Frame(top_row)
        search_box.pack(side="right")
        ttkb.Label(search_box, text="Search:", bootstyle="secondary").pack(side="left", padx=(0, 6))
        self._search_entry = ttkb.Entry(search_box, textvariable=self._search_var, width=26)
        self._search_entry.pack(side="left")

        subtitle_label = ttkb.Label(
            header_frame,
            text="Click a card (or Select) → then press “Place on Layout”.",
            font=("Arial", 10),
            bootstyle="secondary"
        )
        subtitle_label.pack(anchor="w", pady=(0, 8))

        try:
            ttkb.Separator(header_frame).pack(fill="x", pady=(0, 6))
        except Exception:
            pass

        # Scrollable area for cards: Canvas + inner frame + scrollbar
        scroll_container = ttkb.Frame(main_frame, padding=2)
        scroll_container.pack(fill="both", expand=True, pady=(0, 10))

        canvas = tk.Canvas(scroll_container, highlightthickness=0, bd=0)
        vscroll = ttkb.Scrollbar(scroll_container, orient="vertical", command=canvas.yview, bootstyle="round")
        canvas.configure(yscrollcommand=vscroll.set)

        vscroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        grid_frame = ttkb.Frame(canvas)
        self._cards_frame = grid_frame
        self._canvas = canvas
        self._grid_frame = grid_frame
        self._items = list(items)

        canvas.create_window((0, 0), window=grid_frame, anchor="nw")

        def _on_frame_configure(_event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        grid_frame.bind("<Configure>", _on_frame_configure)

        # Initial layout of cards (fixed 3 columns)
        self._layout_cards()

        # Search filter binding
        try:
            self._search_entry.bind("<KeyRelease>", lambda _e: self._apply_filter())
        except Exception:
            pass

        # Footer separator
        try:
            ttkb.Separator(main_frame).pack(fill="x", pady=(0, 6))
        except Exception:
            pass

        # Action buttons frame
        action_frame = ttkb.Frame(main_frame, padding=(0, 4))
        action_frame.pack(fill="x", pady=(10, 0))

        # Place on Layout button
        self.place_button = ttkb.Button(
            action_frame,
            text="Place on Layout",
            command=self._on_place_clicked,
            state="disabled",
            bootstyle="primary"
        )
        self.place_button.pack(side="left", padx=10, pady=6)

        # Cancel button
        cancel_button = ttkb.Button(
            action_frame,
            text="Cancel",
            command=self.dialog.destroy,
            bootstyle="secondary-outline"
        )
        cancel_button.pack(side="right", padx=10, pady=6)

        # Selected item label
        self.selected_label = ttkb.Label(
            action_frame,
            text="No item selected",
            font=("Arial", 12),
            bootstyle="secondary"
        )
        self.selected_label.pack(side="left", padx=10, pady=6)

        # Keyboard shortcuts
        try:
            self.dialog.bind("<Escape>", lambda _e: self.dialog.destroy())
            self.dialog.bind("<Return>", lambda _e: self._on_place_clicked())
        except Exception:
            pass

    def _apply_filter(self):
        """Filter items by search text and refresh layout."""
        q = (self._search_var.get() or "").strip().lower()
        if not q:
            self._items = list(self._all_items)
        else:
            def _norm(s: str) -> str:
                return s.replace("_", " ").lower()

            self._items = [it for it in self._all_items if q in _norm(it)]

        # Clear selection if filtered out
        if self.selected_item and self.selected_item not in self._items:
            self.selected_item = None
            self._selected_card = None
            self.place_button.configure(state="disabled")
            self.selected_label.configure(text="No item selected")

        self._layout_cards()

    def _layout_cards(self):
        """Layout cards in a fixed 3-column grid."""
        frame = self._grid_frame

        # Clear any existing grid placement
        for child in frame.winfo_children():
            child.grid_forget()

        self.cards = []

        # Fixed 3 columns
        cols = 3

        for idx, item_name in enumerate(self._items):
            row = idx // cols
            col = idx % cols
            
            # Debug: print all items being processed
            if item_name.lower() == "tv":
                print(f"[DEBUG] Creating card for 'tv' at row={row}, col={col}")

            try:
                card = self._create_card(frame, item_name)
                if card:  # Only add if card was successfully created
                    card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
                    self.cards.append(card)
                    if item_name.lower() == "tv":
                        print(f"[DEBUG] Successfully created and added 'tv' card")
                else:
                    if item_name.lower() == "tv":
                        print(f"[DEBUG] Warning: 'tv' card creation returned None")
            except Exception as e:
                print(f"Error creating card for {item_name}: {e}")
                import traceback
                traceback.print_exc()
                if item_name.lower() == "tv":
                    print(f"[DEBUG] Exception while creating 'tv' card")

        # Configure 3 columns with equal weight
        for c in range(cols):
            frame.grid_columnconfigure(c, weight=1)

    def _create_card(self, parent, item_name):
        """Create a furniture card with image, name, and size."""
        try:
            # Fixed card size so all cards look consistent
            card_width = 220
            card_height = 250

            card = ttkb.Frame(parent, style="Card.TFrame", width=card_width, height=card_height)
            # Prevent the card from shrinking to fit content
            try:
                card.pack_propagate(False)
            except Exception:
                pass
            try:
                card.grid_propagate(False)
            except Exception:
                pass

            # Use a grid inside the card to keep spacing consistent
            content_frame = ttkb.Frame(card)
            content_frame.pack(fill="both", expand=True)

            # Row layout: image area / name / size / button
            content_frame.grid_rowconfigure(0, weight=1)  # image area takes extra space
            content_frame.grid_rowconfigure(1, weight=0)
            content_frame.grid_rowconfigure(2, weight=0)
            content_frame.grid_rowconfigure(3, weight=0)
            content_frame.grid_columnconfigure(0, weight=1)

            # Image placeholder area (fixed)
            img_box = ttkb.Frame(content_frame, width=160, height=130)
            img_box.grid(row=0, column=0, sticky="n", pady=(8, 6))
            try:
                img_box.pack_propagate(False)
            except Exception:
                pass

            image_path = find_image_path(item_name)
            if image_path:
                try:
                    img = Image.open(image_path).convert("RGBA")
                    # Force a predictable thumbnail size so all cards align
                    img.thumbnail((120, 120), Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(img)
                    image_label = ttkb.Label(img_box, image=photo)
                    image_label.image = photo  # Keep a reference
                    image_label.pack(expand=True)
                except Exception as e:
                    print(f"Error loading image for {item_name}: {e}")
            else:
                # Keep spacing stable even when image is missing
                ttkb.Label(img_box, text="No Image", bootstyle="secondary").pack(expand=True)

            # Item name (wrap so height stays bounded)
            display_name = item_name.replace("_", " ").title()
            name_label = ttkb.Label(
                content_frame,
                text=display_name,
                font=("Arial", 12, "bold"),
                wraplength=200,
                justify="center",
            )
            name_label.grid(row=1, column=0, sticky="n", pady=(0, 4), padx=8)

            # Size information - robust lookup using pre-normalized map (reloads latest sizes)
            try:
                # Reload sizes to get latest values from furniture_sizes.py
                standard_sizes = _get_furniture_sizes()
                normalized_sizes = _get_normalized_sizes()
                norm = _norm_key(item_name)
                size = standard_sizes.get(item_name) or normalized_sizes.get(norm)
                # Debug: print size for tv to verify reload is working
                if item_name.lower() == "tv":
                    print(f"[DEBUG] Card size lookup for 'tv': {size} (from standard_sizes: {standard_sizes.get(item_name)}, normalized: {normalized_sizes.get(norm)})")
                size_text = f"Size: {size[0]}ft × {size[1]}ft" if size else "Size: Not specified"
            except Exception as e:
                print(f"Error getting size for {item_name}: {e}")
                import traceback
                traceback.print_exc()
                size_text = "Size: Not specified"

            size_label = ttkb.Label(
                content_frame,
                text=size_text,
                font=("Arial", 10),
            )
            size_label.grid(row=2, column=0, sticky="n", pady=(0, 8))

            # Select button
            select_btn = ttkb.Button(
                content_frame,
                text="Select",
                command=lambda: self._on_card_selected(item_name, card),
                width=12,
            )
            select_btn.grid(row=3, column=0, sticky="s", pady=(0, 10))

            # Card interactions: click anywhere + hover effect
            def _on_click(_event=None):
                self._on_card_selected(item_name, card)

            try:
                card.bind("<Button-1>", _on_click)
                content_frame.bind("<Button-1>", _on_click)
                img_box.bind("<Button-1>", _on_click)
                name_label.bind("<Button-1>", _on_click)
                size_label.bind("<Button-1>", _on_click)
            except Exception:
                pass

            def _on_enter(_event=None):
                if self._selected_card is not card:
                    try:
                        card.configure(style="CardHover.TFrame")
                    except Exception:
                        pass

            def _on_leave(_event=None):
                if self._selected_card is not card:
                    try:
                        card.configure(style="Card.TFrame")
                    except Exception:
                        pass

            try:
                card.bind("<Enter>", _on_enter)
                card.bind("<Leave>", _on_leave)
                content_frame.bind("<Enter>", _on_enter)
                content_frame.bind("<Leave>", _on_leave)
            except Exception:
                pass

            return card
        except Exception as e:
            print(f"Error in _create_card for {item_name}: {e}")
            import traceback
            traceback.print_exc()
            # Return a minimal card even on error so item still appears
            error_card = ttkb.Frame(parent, style="Card.TFrame", width=220, height=250)
            ttkb.Label(error_card, text=f"{item_name}\n(Error loading)", font=("Arial", 10)).pack(expand=True)
            return error_card

    def _on_card_selected(self, item_name, card):
        """Handle card selection."""
        # Reset all cards to default appearance
        for c in self.cards:
            c.configure(style="Card.TFrame")

        # Highlight selected card
        card.configure(style="CardSelected.TFrame")
        self._selected_card = card

        self.selected_item = item_name
        display_name = item_name.replace("_", " ").title()
        self.selected_label.configure(
            text=f"✓ Selected: {display_name}"
        )
        self.place_button.configure(state="normal")

    def _on_place_clicked(self):
        """Handle Place on Layout button click."""
        if self.selected_item and self.select_callback:
            self.select_callback(self.selected_item)
            self.dialog.destroy()
