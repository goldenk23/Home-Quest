from __future__ import annotations

import re
from typing import Callable, Iterable, Sequence

import os
import sys
import platform
import tkinter as tk

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

try:
    from FurnitureHelper import STANDARD_FURNITURE_SIZES
except Exception:  # pragma: no cover - defensive import
    STANDARD_FURNITURE_SIZES = {}

try:
    from FurnitureHelper.Category import FURNITURE_CATEGORIES
except Exception:  # pragma: no cover - defensive import
    FURNITURE_CATEGORIES = {}


_THIS_DIR = os.path.dirname(os.path.abspath(__file__))


# Shared dialog theme (used for cross‑platform furniture suggestion popup)
_DIALOG_BG = "#fdf4f4"        # soft, non‑harsh background
_DIALOG_MAROON = "#800000"   # primary accent
_DIALOG_HOVER_BG = "#fbe2e2"


class FurnitureSuggester:
    """
    Smart furniture suggester (sklearn based) that only suggests items defined in:
    - `FurnitureHelper/Category.py` (excluding Doors)
    - AND present in `FurnitureHelper/furniture_sizes.py` (when available)
    """

    def __init__(self, *, min_score: float = 0.62, max_items: int = 12) -> None:
        self._min_score = float(min_score)
        self._max_items = int(max_items)

        self._available_norm_to_key = self._build_available_key_map(STANDARD_FURNITURE_SIZES)
        self._allowed_items = self._build_allowed_items_from_categories()

        # Room -> furniture suggestions (strictly from categories)
        self._room_to_items: dict[str, list[str]] = self._build_room_suggestions()
        self._canonical_rooms: tuple[str, ...] = tuple(self._room_to_items.keys())

        # Common user-entered room name variants (EN + common Indian terms).
        self._aliases: dict[str, str] = {
            "room": "living room",
            "hall": "living room",
            "lounge": "living room",
            "drawing room": "living room",
            "sitting": "living room",
            "sitting room": "living room",
            "family room": "living room",
            "livingroom": "living room",
            "baithak": "living room",
            "bed room": "bedroom",
            "master bedroom": "bedroom",
            "kids room": "bedroom",
            "guest room": "bedroom",
            "washroom": "bathroom",
            "restroom": "bathroom",
            "wc": "bathroom",
            "toilet": "bathroom",
            "bath": "bathroom",
            "dining": "dining room",
            "office": "study",
            "work": "study",
            "workroom": "study",
            "parking": "garage",
            "rasoi": "kitchen",
        }

        self._stopwords = {
            "room",
            "area",
            "the",
            "a",
            "an",
            "of",
            "and",
            "for",
            "to",
            "my",
            "our",
            "your",
            "new",
            "old",
            "main",
        }

        # Build phrase->canonical mapping for ML room matching.
        self._phrase_to_room: dict[str, str] = {}
        for room in self._room_to_items:
            self._phrase_to_room[room] = room
        for phrase, room in self._aliases.items():
            self._phrase_to_room[phrase] = room

        self._phrases: list[str] = list(self._phrase_to_room.keys())
        self._vectorizer = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(3, 5),
            lowercase=True,
        )
        self._phrase_matrix = self._vectorizer.fit_transform(self._phrases)

    def suggest(self, input_name: str) -> list[str]:
        room_key = self._infer_room(input_name)
        if not room_key:
            return self._fallback_suggestions(input_name)

        items = self._room_to_items.get(room_key, [])
        items = self._postprocess_items(items, input_name=input_name, room_key=room_key)
        return items

    def _fallback_suggestions(self, input_name: str) -> list[str]:
        """When room name is generic/unknown, still return a useful list (e.g. living room)."""
        norm = self._normalize_room_text(input_name or "")
        if not norm or norm in ("room", "area", "space"):
            items = self._room_to_items.get("living room", [])
            return self._postprocess_items(
                items, input_name=input_name or "Room", room_key="living room"
            )[: self._max_items]
        return []

    def _postprocess_items(self, items: list[str], *, input_name: str, room_key: str) -> list[str]:
        seen: set[str] = set()
        cleaned: list[str] = []

        for it in items:
            if not it:
                continue

            nk = self._norm_key(it)
            if not nk:
                continue

            # Only allow items that exist in categories (excluding doors).
            if self._allowed_items and nk not in self._allowed_items:
                continue

            # If sizes exist, only allow if present there too.
            if self._available_norm_to_key and nk not in self._available_norm_to_key:
                continue

            if nk in seen:
                continue
            seen.add(nk)
            cleaned.append(it)

        # Small personalization that still respects categories.
        norm_room = self._normalize_room_text(input_name)
        if room_key == "bedroom":
            if any(k in norm_room.split() for k in ("kids", "kid", "child", "children")):
                cleaned = self._move_front(cleaned, "single_bed")
            if any(k in norm_room.split() for k in ("master", "main")):
                cleaned = self._move_front(cleaned, "double_bed")

        return cleaned[: self._max_items]

    def _build_room_suggestions(self) -> dict[str, list[str]]:
        def canon(label: str) -> str:
            nk = self._norm_key(label)
            if not nk:
                return ""
            if self._available_norm_to_key:
                return self._available_norm_to_key.get(nk, "")
            return (label or "").strip().lower().replace(" ", "_")

        def from_category(cat: str) -> list[str]:
            raw = (FURNITURE_CATEGORIES or {}).get(cat, []) or []
            out: list[str] = []
            for x in raw:
                k = canon(str(x))
                if k:
                    out.append(k)
            return out

        beds = from_category("Beds")
        bathroom = from_category("Bathroom")
        kitchen = from_category("Kitchen")
        common = from_category("Common Furniture")

        # Living room is a curated subset of Common Furniture (all items still come from categories).
        living_pref_raw = [
            "Sofa_Set_with_Centre_Table",
            "sofa_set_with_centre_table",
            "single_sofa",
            "sofa",
            "tv",
            "Chair",
            "standing_cabinet",
        ]
        living: list[str] = []
        for x in living_pref_raw:
            k = canon(x)
            if k and k not in living:
                living.append(k)
        living += [x for x in common if x not in set(living)]

        # Dining room suggestions derived from Common Furniture (dining tables + table-chair set).
        table_set_norms = {self._norm_key("Table_Chair_Set")}
        dining = [
            x
            for x in common
            if x.startswith("dining_table_") or self._norm_key(x) in table_set_norms
        ]
        for extra in ("Table_Chair_Set", "standing_cabinet"):
            k = canon(extra)
            if k and k not in dining:
                dining.append(k)

        # Study: only items that exist in categories.
        study_raw = ["study_table_chair", "Chair", "standing_cabinet"]
        study = []
        for x in study_raw:
            k = canon(x)
            if k and k not in study:
                study.append(k)

        # Bedroom: beds + (some common storage/seating items from categories)
        bedroom = list(beds)
        for extra in ("wardrobe", "standing_cabinet", "Chair"):
            k = canon(extra)
            if k and k not in bedroom:
                bedroom.append(k)

        # Kitchen: keep as-is (category-based)

        return {
            "kitchen": kitchen,
            "bedroom": bedroom,
            "bathroom": bathroom,
            "living room": living,
            "dining room": dining,
            "study": study,
            # Garage: no category mapping yet
            "garage": [],
        }

    def _infer_room(self, input_name: str) -> str:
        norm = self._normalize_room_text(input_name)
        if not norm:
            return ""

        if norm in self._room_to_items:
            return norm
        if norm in self._aliases:
            return self._aliases[norm]

        tokens = [t for t in norm.split() if t and t not in self._stopwords]
        token_set = set(tokens)

        # Keyword inference first
        if token_set & {"kitchen", "cook", "cooking", "pantry", "rasoi"}:
            return "kitchen"
        if token_set & {"bedroom", "bed", "master", "guest", "kids", "kid", "child", "children"}:
            return "bedroom"
        if token_set & {"bathroom", "bath", "washroom", "toilet", "wc", "restroom"}:
            return "bathroom"
        if token_set & {"living", "hall", "lounge", "drawing", "sitting", "family"}:
            return "living room"
        if token_set & {"dining", "dinner"}:
            return "dining room"
        if token_set & {"study", "office", "work", "library", "reading"}:
            return "study"
        if token_set & {"garage", "parking", "car"}:
            return "garage"

        # ML fuzzy fallback
        try:
            vec = self._vectorizer.transform([norm])
            sims = cosine_similarity(vec, self._phrase_matrix)[0]
        except Exception:
            return ""

        if getattr(sims, "size", 0) == 0:
            return ""

        best_i = int(sims.argmax())
        best_score = float(sims[best_i])
        if best_score < self._min_score:
            return ""

        best_phrase = self._phrases[best_i]
        return self._phrase_to_room.get(best_phrase, "")

    def _build_allowed_items_from_categories(self) -> set[str]:
        cats = FURNITURE_CATEGORIES if isinstance(FURNITURE_CATEGORIES, dict) else {}
        if not cats:
            return set()

        allowed: set[str] = set()
        for cat_name, items in cats.items():
            if str(cat_name).strip().lower() == "doors":
                continue
            if not items:
                continue
            for raw in items:
                nk = self._norm_key(str(raw))
                if not nk:
                    continue
                if self._available_norm_to_key:
                    canonical = self._available_norm_to_key.get(nk, "")
                    if canonical:
                        allowed.add(self._norm_key(canonical))
                        continue
                allowed.add(nk)
        return allowed

    @staticmethod
    def _build_available_key_map(sizes: dict) -> dict[str, str]:
        if not isinstance(sizes, dict) or not sizes:
            return {}

        out: dict[str, str] = {}
        for raw_key in sizes.keys():
            k = str(raw_key)
            nk = FurnitureSuggester._norm_key(k)
            if not nk:
                continue

            preferred = k.strip()
            candidate = preferred.lower().replace(" ", "_")

            existing = out.get(nk)
            if existing is None:
                out[nk] = candidate
            else:
                # Prefer lowercase canonical keys when duplicates exist.
                if existing != existing.lower() and candidate == candidate.lower():
                    out[nk] = candidate
        return out

    @staticmethod
    def _norm_key(s: str) -> str:
        if not s:
            return ""
        t = str(s).strip().lower()
        for ch in (" ", "_", "-"):
            t = t.replace(ch, "")
        return t

    @staticmethod
    def _move_front(items: list[str], item: str) -> list[str]:
        if item not in items:
            return items
        return [item] + [x for x in items if x != item]

    @staticmethod
    def _normalize_room_text(text: str) -> str:
        if not isinstance(text, str):
            return ""
        t = text.strip().lower()
        if not t:
            return ""
        t = t.replace("_", " ").replace("-", " ").replace("/", " ")
        t = re.sub(r"[^a-z0-9 ]+", " ", t)
        t = re.sub(r"\s+", " ", t).strip()
        return t


class FurnitureSuggestionPopup:
    """
    Cross‑platform, minimal popup that shows furniture suggestions in a maroon‑styled grid.

    This class is intentionally UI‑only: it receives a parent window, a title, and a list
    of (label, callback) pairs. The actual placement logic lives in the caller (e.g. model).
    """

    def __init__(
        self,
        parent: tk.Misc,
        title: str,
        buttons: Sequence[tuple[str, Callable[[], None]]],
        columns: int = 3,
    ) -> None:
        self.parent = parent
        self.title = title
        self.buttons = list(buttons)
        self.columns = max(int(columns) if columns else 1, 1)

    def show(self) -> None:
        if not self.buttons:
            return

        root: tk.Misc = (
            self.parent.winfo_toplevel()  # type: ignore[assignment]
            if hasattr(self.parent, "winfo_toplevel")
            else self.parent
        )

        os_name = platform.system()

        use_ctk = False
        use_ttkb = False

        # macOS -> CustomTkinter (CTk)
        if os_name == "Darwin":
            try:
                import customtkinter as ctk  # type: ignore[import]

                use_ctk = True
            except Exception:
                ctk = None  # type: ignore[assignment]
                use_ctk = False

        # Windows -> ttkbootstrap (if available)
        if not use_ctk and os_name == "Windows":
            try:
                import ttkbootstrap as ttkb  # type: ignore[import]

                use_ttkb = True
            except Exception:
                ttkb = None  # type: ignore[assignment]
                use_ttkb = False

        if use_ctk:
            win = ctk.CTkToplevel(root)  # type: ignore[name-defined]
            try:
                win.configure(fg_color=_DIALOG_BG)
            except Exception:
                pass
        else:
            win = tk.Toplevel(root)
            try:
                win.configure(bg=_DIALOG_BG)
            except Exception:
                pass

        win.title(self.title)
        try:
            win.transient(root)
            win.grab_set()
        except Exception:
            pass
        try:
            win.resizable(False, False)
        except Exception:
            pass
        # Best-effort: apply MiniAutoCAD's window icon
        try:
            from Helper.set_window_icon import set_window_icon  # type: ignore[import]

            set_window_icon(win)  # type: ignore[arg-type]
        except Exception:
            pass

        # On macOS, hide native title bar (traffic lights); popup is closed via the
        # in-dialog buttons instead of minimize/zoom controls.
        try:
            if os_name == "Darwin":
                win.overrideredirect(True)
        except Exception:
            pass

        if use_ctk:
            body = ctk.CTkFrame(win, fg_color=_DIALOG_BG)  # type: ignore[name-defined]
        elif use_ttkb:
            body = ttkb.Frame(win, padding=8)  # type: ignore[name-defined]
        else:
            body = tk.Frame(win, bg=_DIALOG_BG)
        body.pack(padx=8, pady=8, fill="both", expand=True)

        # --- Header bar with title + close button ---
        if use_ctk:
            header = ctk.CTkFrame(body, fg_color="#f3f4f6")  # type: ignore[name-defined]
            title_lbl = ctk.CTkLabel(  # type: ignore[name-defined]
                header,
                text=self.title,
                text_color="#111111",
                font=("Arial", 14, "bold"),
            )
            # Match CTK text dialog close button style (rounded red pill)
            close_btn = ctk.CTkButton(  # type: ignore[name-defined]
                header,
                text="✕",
                width=30,
                fg_color="#ef4444",
                hover_color="#dc2626",
                text_color="white",
                corner_radius=15,
                command=win.destroy,
            )
        elif use_ttkb:
            header = ttkb.Frame(body)  # type: ignore[name-defined]
            title_lbl = ttkb.Label(  # type: ignore[name-defined]
                header,
                text=self.title,
                font=("Arial", 11, "bold"),
            )
            close_btn = ttkb.Button(  # type: ignore[name-defined]
                header,
                text="✕",
                width=3,
                bootstyle="danger",
                command=win.destroy,
            )
        else:
            header = tk.Frame(body, bg=_DIALOG_BG)
            title_lbl = tk.Label(
                header,
                text=self.title,
                bg=_DIALOG_BG,
                fg=_DIALOG_MAROON,
                font=("Arial", 11, "bold"),
            )
            close_btn = tk.Button(
                header,
                text="✕",
                width=3,
                fg=_DIALOG_MAROON,
                bg=_DIALOG_BG,
                activeforeground=_DIALOG_MAROON,
                activebackground=_DIALOG_HOVER_BG,
                bd=0,
                command=win.destroy,
            )

        header.pack(fill="x", pady=(0, 6))
        title_lbl.pack(side="left", padx=(2, 0))
        close_btn.pack(side="right", padx=(0, 2))

        # --- Grid of suggestion buttons ---
        if use_ctk:
            grid_frame = ctk.CTkFrame(body, fg_color=_DIALOG_BG)  # type: ignore[name-defined]
        elif use_ttkb:
            grid_frame = ttkb.Frame(body)  # type: ignore[name-defined]
        else:
            grid_frame = tk.Frame(body, bg=_DIALOG_BG)
        grid_frame.pack(fill="both", expand=True)

        cols = self.columns
        for idx, (label, callback) in enumerate(self.buttons):
            row, col = divmod(idx, cols)
            if use_ctk:
                btn = ctk.CTkButton(  # type: ignore[name-defined]
                    grid_frame,
                    text=label,
                    width=110,
                    fg_color=_DIALOG_BG,
                    hover_color=_DIALOG_HOVER_BG,
                    text_color=_DIALOG_MAROON,
                    border_color=_DIALOG_MAROON,
                    border_width=1,
                    corner_radius=6,
                    command=callback,
                )
            elif use_ttkb:
                btn = ttkb.Button(  # type: ignore[name-defined]
                    grid_frame,
                    text=label,
                    width=14,
                    bootstyle="danger-outline",
                    command=callback,
                )
            else:
                btn = tk.Button(
                    grid_frame,
                    text=label,
                    width=18,
                    fg=_DIALOG_MAROON,
                    bg=_DIALOG_BG,
                    activeforeground=_DIALOG_MAROON,
                    activebackground=_DIALOG_HOVER_BG,
                    highlightbackground=_DIALOG_MAROON,
                    highlightcolor=_DIALOG_MAROON,
                    highlightthickness=1,
                    bd=1,
                    relief="solid",
                    command=callback,
                )
            btn.grid(row=row, column=col, padx=6, pady=4, sticky="nsew")

        # Let grid shrink‑wrap content, then center over parent window when possible.
        try:
            for r in range((len(self.buttons) + cols - 1) // cols):
                grid_frame.grid_rowconfigure(r, weight=1)
            for c in range(cols):
                grid_frame.grid_columnconfigure(c, weight=1)
        except Exception:
            pass

        try:
            win.update_idletasks()
            width = win.winfo_reqwidth()
            height = win.winfo_reqheight()

            try:
                root.update_idletasks()
                px = root.winfo_x()
                py = root.winfo_y()
                pw = root.winfo_width()
                ph = root.winfo_height()
                if pw > 0 and ph > 0:
                    x = px + max((pw - width) // 2, 0)
                    y = py + max((ph - height) // 2, 0)
                else:
                    raise RuntimeError("Parent size not ready")
            except Exception:
                sw = win.winfo_screenwidth()
                sh = win.winfo_screenheight()
                x = (sw - width) // 2
                y = (sh - height) // 2

            win.geometry(f"{width}x{height}+{x}+{y}")
        except Exception:
            pass
