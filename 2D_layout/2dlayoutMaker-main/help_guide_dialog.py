# help_guide_dialog.py
import tkinter as tk
import os
import sys
import importlib.util
from Helper.set_window_icon import set_window_icon

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))

# Check if we should use ttkbootstrap (Windows only)
USE_TTKB = False
if sys.platform == "win32":
    try:
        import ttkbootstrap as ttkb
        from ttkbootstrap.scrolled import ScrolledFrame
        USE_TTKB = True
    except ImportError:
        pass

# Resolve CTK & COLORS
try:
    from Helper.ctk_global import ctk
except ModuleNotFoundError:
    _helper_dir = os.path.join(_THIS_DIR, "Helper")
    _ctk_path = os.path.join(_helper_dir, "ctk_global.py")
    _spec = importlib.util.spec_from_file_location("mini_autocad_ctk_global", _ctk_path)
    if _spec and _spec.loader:
        _module = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_module)
        ctk = getattr(_module, "ctk")
    else:
        raise

try:
    from Helper.color_scheme import COLORS
except ModuleNotFoundError:
    _helper_dir = os.path.join(_THIS_DIR, "Helper")
    _color_path = os.path.join(_helper_dir, "color_scheme.py")
    _spec = importlib.util.spec_from_file_location("mini_autocad_color_scheme", _color_path)
    if _spec and _spec.loader:
        _module = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_module)
        COLORS = getattr(_module, "COLORS", {})
    else:
        COLORS = {}


NEW_FEATURE_GUIDES = [
    (
        "✨ Where to find the new tools",
        "Use the purple 'Editing Tools ▼' button in the top toolbar from any sidebar tab.",
        "1. Restart the editor after an update.\n2. Click Editing Tools ▼ beside Save.\n3. Choose Window, line, room, furniture, duplicate, or view actions.\n4. The same actions also appear in Draw, Edit, and Furniture tabs.",
        "If the button is off-screen, use the small ◀/▶ toolbar scroll arrows.",
    ),
    (
        "✏️ Continuous Line drawing and snapping",
        "Draw connected segments with endpoint, midpoint, grid, straight-angle, and perpendicular snapping.",
        "1. Open Draw and click Line.\n2. Click the first point.\n3. Move near existing geometry; the snap marker shows the chosen point.\n4. Click repeatedly to continue connected segments.\n5. Right-click once or press Escape to stop Line mode.",
        "Right-click stops drawing immediately; it should not open a context menu for that click.",
    ),
    (
        "🏠 Create a real room from lines",
        "Convert a clean four-line rectangle into a normal named room.",
        "1. Draw four joined, axis-aligned lines forming one closed rectangle.\n2. Choose Create Room from Closed Lines.\n3. Enter the room name.\n4. Select Filled, Transparent, or Walls Only style.\n5. The source lines become a room with normal room behavior.",
        "This command intentionally rejects open, diagonal, overlapping, or non-rectangular boundaries.",
    ),
    (
        "🪟 Place and edit real windows",
        "Windows now have room, wall, width, position, and type data instead of being only visual gaps.",
        "1. Create a room using the Walls Only style.\n2. Choose Place Window.\n3. Click the target wall.\n4. Enter width and type (sliding, casement, or fixed).\n5. Click the blue window to select it.\n6. Use Move / Edit Selected to change width, wall offset, or type.\n7. Use Delete Selected to remove it and restore the wall.",
        "Window placement only accepts a visible wall of a Walls Only room.",
    ),
    (
        "🪑 Move and resize furniture or doors",
        "Placed items lock by default so room dragging remains safe.",
        "1. Click the furniture item.\n2. Choose Move / Edit Selected.\n3. Drag it to move; drag blue corner handles to resize proportionally.\n4. Use − Size, + Size, or Set Exact Furniture Size for precise changes.\n5. Press Enter to lock/commit the item again.",
        "Keyboard: R rotates clockwise, Shift+R rotates anti-clockwise, 0 resets to the initial orientation, F/V flips, +/- resizes, and Delete removes the selected item.",
    ),
    (
        "⧉ Duplicate and undo furniture changes",
        "Duplicate and delete actions now participate in Undo and Redo.",
        "1. Select furniture or a door.\n2. Choose Duplicate Selected Furniture.\n3. Move the copy and press Enter to lock it.\n4. Use Ctrl+Z to undo duplication/deletion and Ctrl+Y to redo it.",
        "Doors automatically recalculate their wall opening after duplicate, move, delete, undo, or redo.",
    ),
    (
        "🔍 Zoom, Fit Design, and Reset View",
        "Recover the plan quickly while flooring and furniture remain aligned.",
        "1. Use Zoom In/Out in Draw; zoom is limited to a safe range.\n2. Choose Fit Design to fit all plan content on screen.\n3. Choose Reset View to return to 100% zoom and the canvas origin.",
        "Floor textures are automatically resized after zoom; no manual refresh is needed.",
    ),
    (
        "⧉ Duplicate the entire layout",
        "Create a full-plan copy for repeated apartments, alternatives, or upper-floor drafting.",
        "1. Save the current plan first if desired.\n2. Choose Duplicate Entire Layout.\n3. A complete copy appears 40 pixels down-right.\n4. Move or edit the copied rooms and objects normally.",
        "Room and polygon group IDs are regenerated so the copy remains independent.",
    ),
    (
        "💾 Safer loading and complete style saving",
        "Native layouts retain line appearance, furniture dimensions, windows, and current-plan safety.",
        "1. Use Load and choose a native VastuCraft v1.0 JSON/YAML file.\n2. The file is fully validated before the canvas is changed.\n3. Confirm replacement; an automatic before-load backup is created.\n4. Dashed/bold/solid style, color, width, arrows, windows, and furniture sizes restore on reload.",
        "Home Quest .hq.json files are a different format and are rejected without clearing your drawing.",
    ),
    (
        "🛠 Troubleshooting",
        "Quick answers when a feature appears unavailable.",
        "No Editing Tools button → close and restart app.pyw.\nWindow will not place → use a Walls Only room and click directly on its wall.\nFurniture will not move → select it, choose Move / Edit Selected, then drag.\nLine keeps drawing → right-click once or press Escape.\nDesign is lost off-screen → choose Fit Design, then Reset View if needed.\nFile is rejected → verify it is native Layout Maker v1.0, not .hq.json.",
        "The Help Guide is searchable—type any feature or problem above the cards.",
    ),
]

HINDI_FEATURE_GUIDES = [
    (
        "नई सुविधाएँ कहाँ मिलेंगी",
        "ऊपर की टूलबार में Save के पास बैंगनी 'Editing Tools ▼' बटन से सभी नई सुविधाएँ खोलें।",
        "1. अपडेट के बाद ऐप बंद करके दोबारा खोलें।\n2. Editing Tools ▼ पर क्लिक करें।\n3. Window, Line, Room, Furniture, Duplicate या View विकल्प चुनें।\n4. यही विकल्प Draw, Edit और Furniture टैब में भी मिलेंगे।",
        "बटन स्क्रीन से बाहर हो तो टूलबार के छोटे ◀/▶ तीर इस्तेमाल करें।",
    ),
    (
        "लगातार लाइन बनाना और स्नैपिंग",
        "लाइन endpoint, midpoint, grid, सीधी दिशा और perpendicular बिंदु पर अपने-आप जुड़ सकती है।",
        "1. Draw टैब खोलकर Line चुनें।\n2. पहला बिंदु क्लिक करें।\n3. मौजूदा रेखा के पास जाएँ; snap marker सही बिंदु दिखाएगा।\n4. जुड़े हुए भाग बनाने के लिए लगातार क्लिक करें।\n5. लाइन रोकने के लिए एक बार Right-click करें या Escape दबाएँ।",
        "Right-click करते ही Line mode बंद होगा और उस क्लिक पर context menu नहीं खुलेगा।",
    ),
    (
        "लाइनों से असली कमरा बनाएँ",
        "चार साफ आयताकार लाइनों को नाम वाले सामान्य room object में बदलें।",
        "1. चार जुड़ी हुई सीधी लाइनों से बंद rectangle बनाएँ।\n2. Create Room from Closed Lines चुनें।\n3. कमरे का नाम लिखें।\n4. Filled, Transparent या Walls Only style चुनें।\n5. पुरानी लाइनें सामान्य room behavior वाले कमरे में बदल जाएँगी।",
        "खुली, तिरछी, overlap या non-rectangular सीमा स्वीकार नहीं होगी।",
    ),
    (
        "असली Window लगाएँ और बदलें",
        "Window में room, wall, चौड़ाई, स्थान और type की जानकारी save होती है।",
        "1. Walls Only style वाला room बनाएँ।\n2. Place Window चुनें।\n3. जिस wall पर window चाहिए वहाँ क्लिक करें।\n4. width और type (sliding/casement/fixed) लिखें।\n5. चुनने के लिए नीली window पर क्लिक करें।\n6. Move / Edit Selected से width, wall offset या type बदलें।\n7. Delete Selected से window हटाकर wall वापस बनाएँ।",
        "Window केवल Walls Only room की दिखाई देने वाली wall पर लगेगी।",
    ),
    (
        "Furniture या Door को move और resize करें",
        "Room सुरक्षित रहे इसलिए रखा गया furniture पहले lock रहता है।",
        "1. Furniture पर क्लिक करें।\n2. Move / Edit Selected चुनें।\n3. move करने के लिए drag करें; आकार बदलने के लिए नीले corner handles खींचें।\n4. − Size, + Size या Set Exact Furniture Size इस्तेमाल करें।\n5. item दोबारा lock करने के लिए Enter दबाएँ।",
        "Keyboard: R clockwise rotate, Shift+R anti-clockwise rotate, 0 initial orientation reset, F/V flip, +/- resize और Delete item हटाता है।",
    ),
    (
        "Furniture को Duplicate करें और Undo चलाएँ",
        "Furniture और door के Duplicate/Delete पर अब Undo और Redo काम करते हैं।",
        "1. Furniture या door चुनें।\n2. Duplicate Selected Furniture चुनें।\n3. copy को move करके Enter दबाएँ।\n4. बदलाव वापस लेने के लिए Ctrl+Z और फिर लागू करने के लिए Ctrl+Y दबाएँ।",
        "Door को duplicate, move, delete, undo या redo करने पर wall opening अपने-आप update होगी।",
    ),
    (
        "Zoom, Fit Design और Reset View",
        "Flooring और furniture को सही जगह रखते हुए पूरा design आसानी से स्क्रीन पर वापस लाएँ।",
        "1. Draw में Zoom In/Out इस्तेमाल करें; zoom सुरक्षित सीमा में रहेगा।\n2. पूरा plan स्क्रीन पर लाने के लिए Fit Design चुनें।\n3. 100% zoom और canvas origin पर लौटने के लिए Reset View चुनें।",
        "Zoom के बाद floor texture अपने-आप resize होता है; manual refresh की जरूरत नहीं है।",
    ),
    (
        "पूरा Layout Duplicate करें",
        "Repeated apartment, alternative design या upper-floor drafting के लिए पूरे plan की copy बनाएँ।",
        "1. चाहें तो पहले plan save करें।\n2. Duplicate Entire Layout चुनें।\n3. पूरी copy 40 pixels नीचे-दाएँ दिखाई देगी।\n4. copied rooms और objects को सामान्य तरीके से edit करें।",
        "नई copy स्वतंत्र रहे इसलिए room और polygon group IDs दोबारा बनाए जाते हैं।",
    ),
    (
        "सुरक्षित Loading और पूरी Style Saving",
        "Native layout में line style, furniture size, windows और मौजूदा plan की सुरक्षा बनी रहती है।",
        "1. Load से native VastuCraft v1.0 JSON/YAML चुनें।\n2. Canvas बदलने से पहले file validate होगी।\n3. Replacement confirm करें; before-load backup अपने-आप बनेगा।\n4. Dashed/bold/solid style, color, width, arrows, windows और furniture size reload होंगे।",
        "Home Quest .hq.json अलग format है; उसे drawing हटाए बिना reject किया जाएगा।",
    ),
    (
        "समस्या समाधान",
        "नई सुविधा काम न दिखे तो ये आसान समाधान देखें।",
        "Editing Tools नहीं दिखता → app.pyw बंद करके दोबारा खोलें।\nWindow नहीं लगती → Walls Only room बनाकर wall पर क्लिक करें।\nFurniture move नहीं होता → item चुनें, Move / Edit Selected दबाएँ, फिर drag करें।\nLine चलती रहती है → एक बार Right-click या Escape दबाएँ।\nDesign स्क्रीन से बाहर है → Fit Design, फिर जरूरत हो तो Reset View चुनें।\nFile reject होती है → native Layout Maker v1.0 file चुनें, .hq.json नहीं।",
        "Help Guide में ऊपर search box से window, line, furniture, zoom या save खोजें।",
    ),
]

# Pair every new English guide with its Hindi version; search works in either language.
NEW_FEATURE_GUIDES = [
    (
        f"{english[0]} / {hindi[0]}",
        f"{english[1]}\n\nहिंदी: {hindi[1]}",
        f"English:\n{english[2]}\n\nहिंदी:\n{hindi[2]}",
        f"{english[3]}\nसुझाव: {hindi[3]}",
    )
    for english, hindi in zip(NEW_FEATURE_GUIDES, HINDI_FEATURE_GUIDES)
]


def _toggle_full_screen(window, button) -> None:
    """Toggle a help window between its normal size and full screen."""
    full_screen = not bool(window.attributes("-fullscreen"))
    window.attributes("-fullscreen", full_screen)
    button.configure(text="Restore" if full_screen else "⛶ Full Screen")
    if full_screen:
        window.bind("<Escape>", lambda _event: _toggle_full_screen(window, button))


class HelpGuideDialogTTKB(tk.Toplevel):
    """
    An elegant, easy-to-understand tutorial and shortcut guide
    for MiniAutoCAD / VastuCraft. Supporting English & Hindi explanations.
    Uses ttkbootstrap (ttkb) for a native modern Windows theme/styling.
    """

    def __init__(self, parent) -> None:
        super().__init__(parent)
        self.title("Quick Help Guide / मदद निर्देशिका")
        self.geometry("760x680")
        self.minsize(680, 560)
        self.resizable(True, True)
        
        # Window properties
        self.transient(parent)
        set_window_icon(self)
        self.grab_set()  # Make modal
        self.focus_set()
        
        # Center the window
        self.update_idletasks()
        width = 760
        height = 680
        if parent:
            try:
                top_parent = parent.winfo_toplevel()
                parent_x = top_parent.winfo_rootx()
                parent_y = top_parent.winfo_rooty()
                parent_w = top_parent.winfo_width()
                parent_h = top_parent.winfo_height()
                x = parent_x + (parent_w - width) // 2
                y = parent_y + (parent_h - height) // 2
            except Exception:
                x = (self.winfo_screenwidth() - width) // 2
                y = (self.winfo_screenheight() - height) // 2
        else:
            x = (self.winfo_screenwidth() - width) // 2
            y = (self.winfo_screenheight() - height) // 2
            
        # Ensure window is not positioned off screen boundaries
        x = max(10, min(x, self.winfo_screenwidth() - width - 10))
        y = max(35, min(y, self.winfo_screenheight() - height - 40))
        self.geometry(f"{width}x{height}+{x}+{y}")
        
        # Configure styles
        self.style = ttkb.Style()
        self.style.configure(
            "Keycap.TLabel",
            font=("Segoe UI", 10, "bold"),
            background="#E5E7EB",
            foreground="#111827",
            anchor="center",
            padding=(6, 4),
            relief="raised"
        )
        
        # Main layout
        main_frame = ttkb.Frame(self, bootstyle="light")
        main_frame.pack(fill="both", expand=True, padx=12, pady=12)
        
        # Title and full-screen control
        title_row = ttkb.Frame(main_frame, bootstyle="light")
        title_row.pack(fill="x", pady=(10, 15))
        title_label = ttkb.Label(
            title_row,
            text="💡 Quick Help Guide & Keyboard Shortcuts / त्वरित मदद और शॉर्टकट",
            font=("Segoe UI", 15, "bold"),
            bootstyle="primary"
        )
        title_label.pack(side="left", expand=True)
        expand_btn = ttkb.Button(title_row, text="⛶ Full Screen", bootstyle="primary-outline")
        expand_btn.configure(command=lambda: _toggle_full_screen(self, expand_btn))
        expand_btn.pack(side="right", padx=(8, 0))
        
        # Visible bilingual navigation keeps all original help sections available.
        guide_nav = ttkb.Frame(main_frame, bootstyle="light")
        guide_nav.pack(fill="x", padx=5, pady=(0, 5))
        nav_items = (
            ("✨ New Features / नई सुविधाएँ", 0, "primary"),
            ("⌨ Shortcuts / शॉर्टकट", 1, "secondary"),
            ("🧰 Tools / टूल्स", 2, "info"),
            ("🧭 Vastu / वास्तु", 3, "warning"),
        )

        # Tabview / Notebook
        notebook = ttkb.Notebook(main_frame, bootstyle="primary")
        for text, tab_index, style in nav_items:
            ttkb.Button(
                guide_nav,
                text=text,
                bootstyle=f"{style}-outline",
                command=lambda index=tab_index: notebook.select(index),
            ).pack(side="left", fill="x", expand=True, padx=2)
        notebook.pack(fill="both", expand=True, padx=5, pady=5)
        
        controls_tab = ttkb.Frame(notebook)
        feature_tab = ttkb.Frame(notebook)
        tools_tab = ttkb.Frame(notebook)
        vastu_tab = ttkb.Frame(notebook)

        notebook.add(feature_tab, text="✨ New Features")
        notebook.add(controls_tab, text="Controls & Shortcuts")
        notebook.add(tools_tab, text="Tools Overview")
        notebook.add(vastu_tab, text="Vastu Guide")
        notebook.select(feature_tab)

        # Interactive, searchable feature guide. Card headings expand/collapse on click.
        feature_controls = ttkb.Frame(feature_tab)
        feature_controls.pack(fill="x", padx=8, pady=(8, 4))
        ttkb.Label(feature_controls, text="Search guide / सहायता खोजें:", font=("Segoe UI", 10, "bold")).pack(side="left", padx=(0, 6))
        feature_search_var = tk.StringVar()
        feature_search = ttkb.Entry(feature_controls, textvariable=feature_search_var)
        feature_search.pack(side="left", fill="x", expand=True)
        feature_scroll = ScrolledFrame(feature_tab, autohide=True, bootstyle="light")
        feature_scroll.pack(fill="both", expand=True, padx=8, pady=(2, 8))
        feature_card_host = ttkb.Frame(feature_scroll)
        feature_card_host.pack(fill="both", expand=True)
        feature_bodies = []

        def set_all_feature_cards(opened):
            for body, state in feature_bodies:
                if opened and not state["open"]:
                    body.pack(fill="x", padx=10, pady=(0, 8))
                    state["open"] = True
                elif not opened and state["open"]:
                    body.pack_forget()
                    state["open"] = False

        ttkb.Button(feature_controls, text="Expand all / सब खोलें", bootstyle="primary-outline", command=lambda: set_all_feature_cards(True)).pack(side="left", padx=(6, 2))
        ttkb.Button(feature_controls, text="Collapse / बंद करें", bootstyle="secondary-outline", command=lambda: set_all_feature_cards(False)).pack(side="left", padx=2)

        def render_feature_cards(_event=None):
            for child in feature_card_host.winfo_children():
                child.destroy()
            feature_bodies.clear()
            query = feature_search_var.get().strip().lower()
            matches = [guide for guide in NEW_FEATURE_GUIDES if not query or query in " ".join(guide).lower()]
            if not matches:
                ttkb.Label(feature_card_host, text="No matching topic / कोई विषय नहीं मिला। window, line, furniture, zoom, save या load खोजें।", bootstyle="warning").pack(pady=30)
                return
            for index, (title, summary, steps, tip) in enumerate(matches):
                card = ttkb.Frame(feature_card_host, bootstyle="light", padding=6)
                card.pack(fill="x", padx=4, pady=4)
                state = {"open": bool(query) or index == 0}
                body = ttkb.Frame(card, bootstyle="light")

                def toggle(card_body=body, card_state=state):
                    if card_state["open"]:
                        card_body.pack_forget()
                    else:
                        card_body.pack(fill="x", padx=10, pady=(0, 8))
                    card_state["open"] = not card_state["open"]

                ttkb.Button(card, text=title, command=toggle, bootstyle="primary-outline", width=58).pack(fill="x")
                ttkb.Label(body, text=summary, font=("Segoe UI", 10, "bold"), justify="left", wraplength=610).pack(fill="x", pady=(8, 5))
                ttkb.Label(body, text=steps, justify="left", wraplength=610, bootstyle="secondary").pack(fill="x")
                ttkb.Label(body, text=f"💡 Tip: {tip}", justify="left", wraplength=610, bootstyle="info").pack(fill="x", pady=(7, 0))
                if state["open"]:
                    body.pack(fill="x", padx=10, pady=(0, 8))
                feature_bodies.append((body, state))

        feature_search.bind("<KeyRelease>", render_feature_cards)
        render_feature_cards()
        feature_search.focus_set()

        # Populate Controls Tab
        controls_scroll = ScrolledFrame(controls_tab, autohide=True, bootstyle="light")
        controls_scroll.pack(fill="both", expand=True, padx=5, pady=5)
        
        shortcuts_list = [
            ("🖱️ Left Click", "Start drawing / Place points & furniture\n(रेखा बनाना / फर्नीचर स्थापित करना शुरू करें)"),
            ("🖱️ Right Click / ESC", "Finish drawing / Cancel active tool\n(रेखा पूर्ण करें / टूल रद्द करें)"),
            ("⌨️ 'R' Key", "Rotate selected furniture clockwise 15°\n(चुना हुआ फर्नीचर clockwise घुमाएं)"),
            ("⌨️ Shift + 'R'", "Rotate selected furniture anti-clockwise 15°\n(चुना हुआ फर्नीचर anti-clockwise घुमाएं)"),
            ("⌨️ '0' Key", "Reset furniture to its initial orientation\n(फर्नीचर को शुरुआती दिशा में लाएं)"),
            ("⌨️ 'F' Key", "Flip selected furniture horizontally\n(फर्नीचर को क्षैतिज रूप से पलटें)"),
            ("⌨️ 'V' Key", "Flip selected furniture vertically\n(फर्नीचर को लंबवत रूप से पलटें)"),
            ("⌨️ 'Delete' Key", "Delete selected furniture item\n(चुना हुआ फर्नीचर हटाएं)"),
            ("⌨️ Ctrl + Z", "Undo last drawing action\n(पिछला बदलाव वापस लें)"),
            ("⌨️ Ctrl + Y", "Redo undone drawing action\n(वापस लिया बदलाव फिर से लागू करें)"),
            ("⌨️ Ctrl + S", "Save canvas layout immediately\n(कैनवास लेआउट तुरंत सेव करें)")
        ]
        
        for shortcut, desc in shortcuts_list:
            row_frame = ttkb.Frame(controls_scroll)
            row_frame.pack(fill="x", pady=6, padx=5)
            
            lbl_key = ttkb.Label(
                row_frame,
                text=shortcut,
                style="Keycap.TLabel",
                width=24
            )
            lbl_key.pack(side="left", padx=(0, 10))
            
            lbl_desc = ttkb.Label(
                row_frame,
                text=desc,
                font=("Segoe UI", 10),
                bootstyle="secondary",
                justify="left",
                anchor="w"
            )
            lbl_desc.pack(side="left", fill="x", expand=True)

        # Populate Tools Tab
        tools_scroll = ScrolledFrame(tools_tab, autohide=True, bootstyle="light")
        tools_scroll.pack(fill="both", expand=True, padx=5, pady=5)
        
        tools_desc = [
            ("✏️ Draw Tab", "Draw lines/walls, create custom closed polygons, fill regions with colors, add text labels, or apply flooring styles (wood, tile, marble)."),
            ("🏠 Room Tab", "Instantly add pre-defined room sizes (rectangular, L-shaped, balcony) and place doors, windows, or a directional compass."),
            ("🪑 Furniture Tab", "Choose from common household categories (Beds, Sofas, Kitchen, TV, etc.) and place them seamlessly inside your rooms."),
            ("📍 Coordinates Tab", "Input numerical (x,y) measurements to draw shapes with millimeter/pixel precision."),
            ("⬜ Layout Tab", "Automatically design random layout boundaries with pre-defined configurations.")
        ]
        
        for name, desc in tools_desc:
            lbl_title = ttkb.Label(
                tools_scroll,
                text=name,
                font=("Segoe UI", 12, "bold"),
                bootstyle="primary",
                anchor="w"
            )
            lbl_title.pack(fill="x", padx=10, pady=(8, 2))
            
            lbl_body = ttkb.Label(
                tools_scroll,
                text=desc,
                font=("Segoe UI", 10),
                bootstyle="secondary",
                justify="left",
                anchor="w",
                wraplength=500
            )
            lbl_body.pack(fill="x", padx=10, pady=(0, 8))

        # Populate Vastu Tab
        vastu_scroll = ScrolledFrame(vastu_tab, autohide=True, bootstyle="light")
        vastu_scroll.pack(fill="both", expand=True, padx=5, pady=5)
        
        vastu_tips = [
            ("🧭 Vastu Polygon", "Select Vastu Tab, click 'Create Vastu Polygon', and click vertices around your layout boundary to generate the Vastu Wheel."),
            ("🗺️ Zone Splits", "You can split your layout into 8, 16, or 32 zones. Set the 32 zones mode to Vedic or Moderne Vastu as needed."),
            ("📐 Measuring Directions", "Ensure the North Direction (usually upwards) aligns with your Vastu compass to correctly locate Entrance (Dehleez), Kitchen, Bed, and Toilet locations.")
        ]
        
        for title, desc in vastu_tips:
            lbl_title = ttkb.Label(
                vastu_scroll,
                text=title,
                font=("Segoe UI", 12, "bold"),
                bootstyle="warning",
                anchor="w"
            )
            lbl_title.pack(fill="x", padx=10, pady=(8, 2))
            
            lbl_body = ttkb.Label(
                vastu_scroll,
                text=desc,
                font=("Segoe UI", 10),
                bootstyle="secondary",
                justify="left",
                anchor="w",
                wraplength=500
            )
            lbl_body.pack(fill="x", padx=10, pady=(0, 8))
            
        # Close button
        close_btn = ttkb.Button(
            main_frame,
            text="Close / बंद करें",
            command=self.destroy,
            bootstyle="danger",
            width=18
        )
        close_btn.pack(pady=12)
        
        # Keyboard ESC shortcut to close
        self.bind("<Escape>", lambda _e: self.destroy())


class HelpGuideDialogCTK(ctk.CTkToplevel):
    """
    An elegant, easy-to-understand tutorial and shortcut guide
    for MiniAutoCAD / VastuCraft. Supporting English & Hindi explanations.
    Uses CustomTkinter (ctk) for fallback platforms.
    """

    def __init__(self, parent) -> None:
        super().__init__(parent)
        self.title("Quick Help Guide / मदद निर्देशिका")
        self.geometry("760x680")
        self.minsize(680, 560)
        self.resizable(True, True)
        
        # Bring to front
        self.lift()
        self.focus_force()
        self.grab_set()  # Make modal
        
        # Main layout
        main_frame = ctk.CTkFrame(self, fg_color=COLORS.get("surface", "#F9FAFB"))
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Title and full-screen control
        title_row = ctk.CTkFrame(main_frame, fg_color="transparent")
        title_row.pack(fill="x", pady=(10, 15))
        ctk.CTkLabel(
            title_row,
            text="💡 Quick Help Guide & Keyboard Shortcuts / त्वरित मदद और शॉर्टकट",
            font=("Segoe UI", 16, "bold"),
            text_color=COLORS.get("primary", "#4F46E5")
        ).pack(side="left", expand=True)
        expand_btn = ctk.CTkButton(title_row, text="⛶ Full Screen", width=110, height=30)
        expand_btn.configure(command=lambda: _toggle_full_screen(self, expand_btn))
        expand_btn.pack(side="right", padx=(8, 0))
        
        # Tabview
        tabview = ctk.CTkTabview(
            main_frame,
            segmented_button_selected_color=COLORS.get("primary", "#4F46E5"),
            segmented_button_selected_hover_color=COLORS.get("primary_hover", "#4338CA")
        )
        tabview.pack(fill="both", expand=True, padx=5, pady=5)
        
        controls_tab = tabview.add("Controls & Shortcuts")
        feature_tab = tabview.add("New Features")
        tools_tab = tabview.add("Tools Overview")
        vastu_tab = tabview.add("Vastu Guide")
        tabview.set("New Features")

        feature_controls = ctk.CTkFrame(feature_tab, fg_color="transparent")
        feature_controls.pack(fill="x", pady=(4, 6))
        ctk.CTkLabel(feature_controls, text="Search guide / सहायता खोजें:", font=("Segoe UI", 10, "bold")).pack(side="left", padx=(4, 6))
        feature_search_var = tk.StringVar()
        feature_search = ctk.CTkEntry(feature_controls, textvariable=feature_search_var, placeholder_text="window, line, furniture, zoom...")
        feature_search.pack(side="left", fill="x", expand=True)
        feature_scroll = ctk.CTkScrollableFrame(feature_tab, fg_color="transparent")
        feature_scroll.pack(fill="both", expand=True)
        feature_bodies = []

        def set_all_feature_cards(opened):
            for body, state in feature_bodies:
                if opened and not state["open"]:
                    body.pack(fill="x", padx=8, pady=(0, 6))
                    state["open"] = True
                elif not opened and state["open"]:
                    body.pack_forget()
                    state["open"] = False

        ctk.CTkButton(feature_controls, text="Expand / सब खोलें", width=96, height=28, command=lambda: set_all_feature_cards(True)).pack(side="left", padx=(6, 2))
        ctk.CTkButton(feature_controls, text="Collapse / बंद", width=92, height=28, fg_color=COLORS.get("text_secondary", "#6B7280"), command=lambda: set_all_feature_cards(False)).pack(side="left", padx=2)

        def render_feature_cards(_event=None):
            for child in feature_scroll.winfo_children():
                child.destroy()
            feature_bodies.clear()
            query = feature_search_var.get().strip().lower()
            matches = [guide for guide in NEW_FEATURE_GUIDES if not query or query in " ".join(guide).lower()]
            if not matches:
                ctk.CTkLabel(feature_scroll, text="No matching topic / कोई विषय नहीं मिला। window, line, furniture, zoom, save या load खोजें।", text_color=COLORS.get("warning", "#F59E0B")).pack(pady=30)
                return
            for index, (title, summary, steps, tip) in enumerate(matches):
                card = ctk.CTkFrame(feature_scroll, fg_color=COLORS.get("surface", "#F9FAFB"), border_width=1, border_color=COLORS.get("border", "#E5E7EB"))
                card.pack(fill="x", padx=4, pady=4)
                state = {"open": bool(query) or index == 0}
                body = ctk.CTkFrame(card, fg_color="transparent")

                def toggle(card_body=body, card_state=state):
                    if card_state["open"]:
                        card_body.pack_forget()
                    else:
                        card_body.pack(fill="x", padx=8, pady=(0, 6))
                    card_state["open"] = not card_state["open"]

                ctk.CTkButton(card, text=title, command=toggle, anchor="w", height=34, fg_color=COLORS.get("primary", "#4F46E5")).pack(fill="x", padx=5, pady=5)
                ctk.CTkLabel(body, text=summary, font=("Segoe UI", 10, "bold"), justify="left", anchor="w", wraplength=570).pack(fill="x", pady=(5, 4))
                ctk.CTkLabel(body, text=steps, justify="left", anchor="w", wraplength=570, text_color=COLORS.get("text_secondary", "#6B7280")).pack(fill="x")
                ctk.CTkLabel(body, text=f"💡 Tip: {tip}", justify="left", anchor="w", wraplength=570, text_color=COLORS.get("info", "#3B82F6")).pack(fill="x", pady=(6, 0))
                if state["open"]:
                    body.pack(fill="x", padx=8, pady=(0, 6))
                feature_bodies.append((body, state))

        feature_search.bind("<KeyRelease>", render_feature_cards)
        render_feature_cards()

        # Populate Controls Tab
        controls_scroll = ctk.CTkScrollableFrame(controls_tab, fg_color="transparent")
        controls_scroll.pack(fill="both", expand=True)
        
        shortcuts_list = [
            ("🖱️ Left Click", "Start drawing / Place points & furniture\n(रेखा बनाना / फर्नीचर स्थापित करना शुरू करें)"),
            ("🖱️ Right Click / ESC", "Finish drawing / Cancel active tool\n(रेखा पूर्ण करें / टूल रद्द करें)"),
            ("⌨️ 'R' Key", "Rotate selected furniture clockwise 15°\n(चुना हुआ फर्नीचर clockwise घुमाएं)"),
            ("⌨️ Shift + 'R'", "Rotate selected furniture anti-clockwise 15°\n(चुना हुआ फर्नीचर anti-clockwise घुमाएं)"),
            ("⌨️ '0' Key", "Reset furniture to its initial orientation\n(फर्नीचर को शुरुआती दिशा में लाएं)"),
            ("⌨️ 'F' Key", "Flip selected furniture horizontally\n(फर्नीचर को क्षैतिज रूप से पलटें)"),
            ("⌨️ 'V' Key", "Flip selected furniture vertically\n(फर्नीचर को लंबवत रूप से पलटें)"),
            ("⌨️ 'Delete' Key", "Delete selected furniture item\n(चुना हुआ फर्नीचर हटाएं)"),
            ("⌨️ Ctrl + Z", "Undo last drawing action\n(पिछला बदलाव वापस लें)"),
            ("⌨️ Ctrl + Y", "Redo undone drawing action\n(वापस लिया बदलाव फिर से लागू करें)"),
            ("⌨️ Ctrl + S", "Save canvas layout immediately\n(कैनवास लेआउट तुरंत सेव करें)")
        ]
        
        for shortcut, desc in shortcuts_list:
            row_frame = ctk.CTkFrame(controls_scroll, fg_color="transparent")
            row_frame.pack(fill="x", pady=4)
            
            lbl_key = ctk.CTkLabel(
                row_frame,
                text=shortcut,
                font=("Segoe UI", 11, "bold"),
                fg_color=COLORS.get("border", "#E5E7EB"),
                text_color=COLORS.get("text_primary", "#111827"),
                corner_radius=4,
                width=140,
                height=26
            )
            lbl_key.pack(side="left", padx=5)
            
            lbl_desc = ctk.CTkLabel(
                row_frame,
                text=desc,
                font=("Segoe UI", 10),
                text_color=COLORS.get("text_secondary", "#6B7280"),
                anchor="w",
                justify="left"
            )
            lbl_desc.pack(side="left", fill="x", expand=True, padx=10)

        # Populate Tools Tab
        tools_scroll = ctk.CTkScrollableFrame(tools_tab, fg_color="transparent")
        tools_scroll.pack(fill="both", expand=True)
        
        tools_desc = [
            ("✏️ Draw Tab", "Draw lines/walls, create custom closed polygons, fill regions with colors, add text labels, or apply flooring styles (wood, tile, marble)."),
            ("🏠 Room Tab", "Instantly add pre-defined room sizes (rectangular, L-shaped, balcony) and place doors, windows, or a directional compass."),
            ("🪑 Furniture Tab", "Choose from common household categories (Beds, Sofas, Kitchen, TV, etc.) and place them seamlessly inside your rooms."),
            ("📍 Coordinates Tab", "Input numerical (x,y) measurements to draw shapes with millimeter/pixel precision."),
            ("⬜ Layout Tab", "Automatically design random layout boundaries with pre-defined configurations.")
        ]
        
        for name, desc in tools_desc:
            lbl_title = ctk.CTkLabel(
                tools_scroll,
                text=name,
                font=("Segoe UI", 12, "bold"),
                text_color=COLORS.get("primary", "#4F46E5"),
                anchor="w"
            )
            lbl_title.pack(fill="x", padx=10, pady=(6, 2))
            
            lbl_body = ctk.CTkLabel(
                tools_scroll,
                text=desc,
                font=("Segoe UI", 10),
                text_color=COLORS.get("text_secondary", "#6B7280"),
                justify="left",
                anchor="w",
                wraplength=440
            )
            lbl_body.pack(fill="x", padx=10, pady=(0, 6))

        # Populate Vastu Tab
        vastu_scroll = ctk.CTkScrollableFrame(vastu_tab, fg_color="transparent")
        vastu_scroll.pack(fill="both", expand=True)
        
        vastu_tips = [
            ("🧭 Vastu Polygon", "Select Vastu Tab, click 'Create Vastu Polygon', and click vertices around your layout boundary to generate the Vastu Wheel."),
            ("🗺️ Zone Splits", "You can split your layout into 8, 16, or 32 zones. Set the 32 zones mode to Vedic or Moderne Vastu as needed."),
            ("📐 Measuring Directions", "Ensure the North Direction (usually upwards) aligns with your Vastu compass to correctly locate Entrance (Dehleez), Kitchen, Bed, and Toilet locations.")
        ]
        
        for title, desc in vastu_tips:
            lbl_title = ctk.CTkLabel(
                vastu_scroll,
                text=title,
                font=("Segoe UI", 12, "bold"),
                text_color=COLORS.get("warning", "#F59E0B"),
                anchor="w"
            )
            lbl_title.pack(fill="x", padx=10, pady=(6, 2))
            
            lbl_body = ctk.CTkLabel(
                vastu_scroll,
                text=desc,
                font=("Segoe UI", 10),
                text_color=COLORS.get("text_secondary", "#6B7280"),
                justify="left",
                anchor="w",
                wraplength=440
            )
            lbl_body.pack(fill="x", padx=10, pady=(0, 6))
            
        # Close button
        close_btn = ctk.CTkButton(
            main_frame,
            text="Close / बंद करें",
            command=self.destroy,
            fg_color=COLORS.get("error", "#EF4444"),
            hover_color="#DC2626",
            height=32,
            corner_radius=6,
            text_color="#FFFFFF"
        )
        close_btn.pack(pady=10)


# Dynamically bind HelpGuideDialog to the platform-appropriate class
if USE_TTKB:
    HelpGuideDialog = HelpGuideDialogTTKB
else:
    HelpGuideDialog = HelpGuideDialogCTK

