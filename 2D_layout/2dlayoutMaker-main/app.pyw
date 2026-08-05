import json
import os
import sys
import tkinter as tk
from tkinter import filedialog  # std Tk works fine with CTk
from pathlib import Path
import psutil
try:
    import ctypes
except ImportError:
    ctypes = None

# Ensure this folder is on sys.path so local imports work when this file is loaded
# via file-path (e.g., VastuApp importing app.pyw using importlib/runpy).
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
try:
    if _THIS_DIR in sys.path:
        sys.path.remove(_THIS_DIR)
except Exception:
    pass
sys.path.insert(0, _THIS_DIR)

# Keep project root available too (some parent app imports may rely on it).
PROJECT_ROOT = os.path.dirname(os.path.dirname(_THIS_DIR))
try:
    if PROJECT_ROOT in sys.path:
        sys.path.remove(PROJECT_ROOT)
except Exception:
    pass
# Keep project root right after this module's folder.
sys.path.insert(1, PROJECT_ROOT)

# If the parent Vastu app already imported its own `Helper` package, it can collide with
# MiniAutoCAD's bundled `2dlayoutMaker/Helper`. Clear any preloaded Helper modules so
# subsequent `from Helper.*` imports resolve to THIS app's helper folder.
try:
    for _k in list(sys.modules.keys()):
        if _k == "Helper" or _k.startswith("Helper."):
            del sys.modules[_k]
except Exception:
    pass

import datetime
import faulthandler

# app.pyw runs without a console, so tracebacks printed to stderr are discarded and
# every crash looks silent. Mirror them to a file next to the app so a reproduction can
# actually be diagnosed. faulthandler additionally catches hard faults (segfault, stack
# overflow) that never reach a Python except hook.
_CRASH_LOG_PATH = os.path.join(_THIS_DIR, "crash.log")


def _append_crash_log(header: str, exc, val, tb) -> None:
    try:
        import traceback as _tb
        with open(_CRASH_LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(f"\n===== {header} @ {datetime.datetime.now().isoformat()} =====\n")
            _tb.print_exception(exc, val, tb, file=fh)
    except Exception:
        pass


try:
    _faulthandler_fh = open(_CRASH_LOG_PATH, "a", encoding="utf-8")
    faulthandler.enable(file=_faulthandler_fh)
except Exception:
    _faulthandler_fh = None


def _log_uncaught(exc, val, tb):
    _append_crash_log("UNCAUGHT", exc, val, tb)
    sys.__excepthook__(exc, val, tb)


sys.excepthook = _log_uncaught

from action import ActionManager
from app_paths import AppPathManager
from controller import CanvasController
from Helper.set_window_icon import set_window_icon
from Helper.showMessage import show_message
from Helper.ctk_global import ctk, patch_tk_root
from Helper.color_scheme import COLORS
from layout_serializer import LayoutSerializer
from local_autosave import LocalAutosave
from parity_toolbar import ParityToolbar
from model import CanvasModel
from tools import CanvasTools
from top_action_toolbar import TopActionToolbar
from toolbar import setup_toolbar  # your toolbar.py
from view import CanvasView
from embedded_viewer import EmbeddedViewerRuntime

# collab_on = tk.BooleanVar(value=True)






def launch_app() -> None:
    MiniAutoCADApp().run()


def _parse_parent_pid(argv: list[str]) -> int:
    """Parse --parent-pid <pid> argument."""
    try:
        if "--parent-pid" in argv:
            idx = argv.index("--parent-pid")
            if idx + 1 < len(argv):
                return int(argv[idx + 1])
    except Exception:
        pass
    return 0

def _parse_ready_file(argv: list[str]) -> str:
    """
    HomeScreen passes: --vastu-ready-file <path>
    We touch this file once UI is initialized so HomeScreen loader can close.
    """
    try:
        if "--vastu-ready-file" in argv:
            i = argv.index("--vastu-ready-file")
            if i + 1 < len(argv):
                return str(argv[i + 1])
    except Exception:
        pass
    return ""


class MiniAutoCADApp:
    """MiniAutoCAD app wrapper (class-based) while keeping launch_app() entrypoint."""

    def __init__(self) -> None:
        self._ready_file_path = _parse_ready_file(sys.argv)
        self._parent_pid = _parse_parent_pid(sys.argv)
        self.root = tk.Tk()
        self._app_alive = True
        # Ensure Tk/ttk scale matches CustomTkinter scaling (especially on Windows DPI).
        patch_tk_root(self.root)
        self.root.title("VastuCraft Pro")
        self.root.geometry("1400x800")
        self._min_window_width = None
        self._min_window_height = 520

        try:
            self.root.bind("<Destroy>", self._on_root_destroy)
        except Exception:
            pass

        try:
            self.root.report_callback_exception = self._report_callback_exception
        except Exception:
            pass

        try:
            self.root.tk.createcommand("bgerror", self._bgerror)
        except Exception:
            pass

        # Apply shared VastuApp window icon for consistent branding
        try:
            set_window_icon(self.root)
        except Exception as e:
            print(f"[MiniAutoCAD] Warning: could not set window icon: {e}")

        # Blend the native Windows title bar into the dark navbar without replacing
        # standard minimize/maximize/close behavior.
        if os.name == "nt" and ctypes is not None:
            try:
                self.root.update_idletasks()
                hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
                enabled = ctypes.c_int(1)
                for attribute in (20, 19):
                    result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                        hwnd,
                        attribute,
                        ctypes.byref(enabled),
                        ctypes.sizeof(enabled),
                    )
                    if result == 0:
                        break
            except Exception:
                pass

        # Main frame contains the dark contextual sidebar and the light CAD workspace.
        self.root.configure(bg=COLORS["workspace_header"])
        self.main_frame = tk.Frame(self.root, bg=COLORS["workspace_header"], bd=0)
        self.main_frame.pack(fill="both", expand=True)

        # Right column: canvas + always-visible global actions.
        self.right_frame = tk.Frame(self.main_frame, bg=COLORS["workspace_header"], bd=0)
        self.right_frame.pack(side="right", fill="both", expand=True)

        self.canvas_toolbar_host = tk.Frame(
            self.right_frame, bg=COLORS["workspace_header"], bd=0
        )
        self.canvas_toolbar_host.pack(side="top", fill="x")

        # Rounded segmented workspace switch; use dark background matching navbar
        self.workspace_tabs = ctk.CTkFrame(
            self.canvas_toolbar_host,
            fg_color="#081321",
            corner_radius=0,
            width=264,
            height=42,
        )
        self.workspace_tabs.pack(side="right", fill="y", padx=(3, 7), pady=5)
        self.workspace_tabs.pack_propagate(False)

        tab_options = {
            "width": 80,
            "height": 32,
            "corner_radius": 6,
            "border_width": 1,
            "bg_color": COLORS["surface_dark"],
            "font": ("Segoe UI", 10, "bold"),
            "cursor": "hand2",
        }
        self.plan_tab_button = ctk.CTkButton(
            self.workspace_tabs,
            text="▦  Plan",
            command=self._show_plan,
            **tab_options,
        )
        self.plan_tab_button.pack(side="left", padx=(4, 2), pady=4)
        self.viewer_tab_button = ctk.CTkButton(
            self.workspace_tabs,
            text="⬡  3D View",
            command=self._show_viewer,
            **tab_options,
        )
        self.viewer_tab_button.pack(side="left", padx=(2, 2), pady=4)
        self.split_tab_button = ctk.CTkButton(
            self.workspace_tabs,
            text="⚏  Split",
            command=self._show_split,
            **tab_options,
        )
        self.split_tab_button.pack(side="left", padx=(2, 4), pady=4)

        # Preserve the original canvas parent, coordinates, tags, and event dispatch.
        self.workspace_content = tk.Frame(
            self.right_frame, bg=COLORS["canvas_chrome"], bd=0
        )
        self.workspace_content.pack(side="top", fill="both", expand=True)
        self.workspace_content.grid_rowconfigure(0, weight=1)
        self.workspace_content.grid_columnconfigure(0, weight=1)
        self.canvas_container = tk.Frame(self.workspace_content, bg=COLORS["surface_raised"], bd=0)
        self.canvas_container.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)
        self.viewer_container = tk.Frame(
            self.workspace_content, bg=COLORS["canvas_bg"], bd=0
        )
        self._workspace_mode = "plan"
        self._viewer_after_id = None
        self._detect_after_id = None
        self._set_workspace_tab_style("plan")

        # Step 1: Core app objects
        self.model = CanvasModel()
        self.actions = ActionManager()  # Tools will be set after tools is created

        # Step 2: Setup canvas first (RIGHT side)
        self.view = CanvasView(self.canvas_container, self.model)  # contains .canvas
        self.tools = CanvasTools(self.root, self.model, self.view, self.actions)
        self.actions.tools = self.tools  # Set tools reference for undo/redo cleanup
        self.view.tools = self.tools  # Set tools reference for zoom updates
        self.controller = CanvasController(self.root, self.model, self.view, self.tools, self.actions)
        self.model.tools = self.tools
        self.serializer = LayoutSerializer(self.model, self.view, self.tools, self.actions)
        self.viewer_runtime = EmbeddedViewerRuntime(
            self.root, self.viewer_container, self._refresh_3d
        )

        # Keep project/floor authoring controls in a dropdown to preserve canvas space.
        self.parity_toolbar = ParityToolbar(self.root, self.serializer)
        self.top_toolbar = TopActionToolbar(
            self.canvas_toolbar_host, self.controller, self.actions, self.tools, self.serializer,
            on_project_tools=self.parity_toolbar.toggle,
        )

        # ---- Centralized paths for saved layouts (AppData/local/VastuApp/...) ----
        AppPathManager.ensure_directories()
        self.save_dir = AppPathManager.get_saved_layouts_dir()
        self.local_autosave_path = AppPathManager.get_autosave_file()
        self.backups_dir = AppPathManager.get_backups_dir()

        # ---- Local autosave: always ON (crash-safe) ----
        self.autosaver = LocalAutosave(
            self.root,
            self.serializer,
            self.actions,
            path=self.local_autosave_path,
            save_every_action=True,
            throttle_ms=2000,
            backups_dir=self.backups_dir,
            keep_last=10,
            heartbeat_sec=0,
        )
        self.actions.post_mutation_callback = self._on_project_mutation

        self._setup_toolbar()

        # Final shell styling is applied after CTk/ttk builders, which otherwise can
        # restore theme defaults behind fixed controls and dull the workspace tabs.
        # Reapply legacy Tk shell colors after ttk/CTk builders, which may restore
        # the native light theme behind otherwise dark glass surfaces.
        self.root.configure(bg=COLORS.get("workspace_header", "#081321"))
        self.main_frame.configure(bg=COLORS.get("workspace_header", "#081321"))
        self.right_frame.configure(bg=COLORS.get("workspace_header", "#081321"))
        self.workspace_content.configure(bg=COLORS.get("canvas_chrome", "#101E32"))
        self.canvas_container.configure(bg=COLORS.get("surface_raised", "#0D1A2D"))
        self.viewer_container.configure(bg=COLORS.get("canvas_bg", "#091426"))
        # Ensure canvas_toolbar_host matches workspace_header to prevent white boxes
        self.canvas_toolbar_host.configure(bg=COLORS.get("workspace_header", "#081321"))
        # workspace_tabs colors already set at creation to match workspace_header
        self.plan_tab_button.configure(corner_radius=9)
        self.viewer_tab_button.configure(corner_radius=9)
        self.split_tab_button.configure(corner_radius=9)
        self.view.container.configure(bg=COLORS.get("canvas_bg", "#0B162B"))
        self.view.canvas.configure(bg=COLORS.get("canvas_bg", "#0B162B"))
        # ttkbootstrap theme rebuild reconfigures plain tk.Canvas backgrounds
        # to white; force the toolbar scroll canvas back to the navbar color.
        self.top_toolbar._scroll_canvas.configure(bg=COLORS.get("workspace_header", "#081321"))
        self.root.after_idle(self._set_workspace_tab_style, self._workspace_mode)

        # Grid needs real canvas dimensions; draw after Tk has computed geometry.
        self.root.after_idle(self.view.draw_grid)
        self.root.after(0, self._signal_ready)
        
        # Register cleanup handler for window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

        # Start parent process watcher if PID was provided
        if self._parent_pid > 0:
            self.root.after(2000, self._check_parent_alive)

    def _check_parent_alive(self) -> None:
        """Periodically check if the parent VastuApp process is still running."""
        if not self._app_alive:
            return

        parent_alive = True
        if self._parent_pid > 0:
            try:
                parent_alive = psutil.pid_exists(self._parent_pid)
            except Exception:
                # Fallback: check if process exists using OS-specific methods
                if os.name == 'nt' and ctypes:
                    try:
                        # PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
                        process_handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, self._parent_pid)
                        if process_handle:
                            ctypes.windll.kernel32.CloseHandle(process_handle)
                            parent_alive = True
                        else:
                            parent_alive = False
                    except Exception:
                        parent_alive = True # Assume alive on error
                else:
                    try:
                        os.kill(self._parent_pid, 0)
                        parent_alive = True
                    except OSError:
                        parent_alive = False

        if not parent_alive:
            print(f"[MiniAutoCAD] Parent process {self._parent_pid} terminated. Closing...")
            self._on_closing()
            return

        # Check again in 2 seconds
        if self._app_alive:
            self.root.after(2000, self._check_parent_alive)

    def _signal_ready(self) -> None:
        """Signal HomeScreen loader that the window is ready."""
        if not self._ready_file_path:
            return
        try:
            if self._ready_file_path:
                Path(self._ready_file_path).touch()
            p = Path(self._ready_file_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            # Touch file
            p.write_text("ready", encoding="utf-8")
        except Exception:
            pass

    def _load_local_last(self) -> None:
        try:
            with open(self.local_autosave_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.serializer.load_document(data, confirm=False)
            show_message("info", "Load Local", "Loaded last autosave.")
        except FileNotFoundError:
            show_message("warning", "Load Local", f"No autosave found at:\n{self.local_autosave_path}")
        except Exception as e:
            show_message("error", "Load Local", f"Failed to load autosave:\n{e}")

    def _load_local_from_file(self) -> None:
        initial_dir = self.save_dir if os.path.isdir(self.save_dir) else AppPathManager.get_app_root()
        path = filedialog.askopenfilename(
            title="Open Local Layout",
            initialdir=initial_dir,
            filetypes=[("Layout JSON", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.serializer.load_document(data, confirm=False)
            show_message("info", "Load Local", f"Loaded:\n{os.path.basename(path)}")
        except Exception as e:
            show_message("error", "Load Local", f"Failed to load:\n{e}")

    def _set_workspace_tab_style(self, mode: str) -> None:
        selected = {
            "fg_color": COLORS.get("primary_surface", "#153B3D"),
            "text_color": "#FFFFFF",
            "hover_color": COLORS.get("secondary", "#0F766E"),
            "border_color": COLORS.get("primary", "#2DD4BF"),
        }
        idle = {
            "fg_color": COLORS.get("surface_muted", "#263449"),
            "text_color": "#F8FAFC",
            "hover_color": COLORS.get("surface", "#1E293B"),
            "border_color": COLORS.get("border_strong", "#3A4A61"),
        }
        self.plan_tab_button.configure(
            text="▦  Plan",
            **(selected if mode == "plan" else idle),
        )
        self.viewer_tab_button.configure(
            text="⬡  3D View",
            **(selected if mode == "viewer" else idle),
        )
        self.split_tab_button.configure(
            text="⚏  Split",
            **(selected if mode == "split" else idle),
        )

    def _show_plan(self) -> None:
        if self._workspace_mode == "plan":
            return
        self.viewer_runtime.deactivate()
        self.viewer_container.grid_remove()
        # Reset grid to single column (remove uniform constraint)
        self.workspace_content.grid_columnconfigure(0, weight=1, uniform="")
        self.workspace_content.grid_columnconfigure(1, weight=0, uniform="")
        self.canvas_container.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)
        self._workspace_mode = "plan"
        self._schedule_viewer_refresh()
        self._set_workspace_tab_style("plan")
        self.root.after_idle(self.view.schedule_grid_redraw)

    def _show_viewer(self) -> None:
        self.canvas_container.grid_remove()
        # Reset grid to single column (remove uniform constraint)
        self.workspace_content.grid_columnconfigure(0, weight=1, uniform="")
        self.workspace_content.grid_columnconfigure(1, weight=0, uniform="")
        self.viewer_container.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)
        self._workspace_mode = "viewer"
        self._set_workspace_tab_style("viewer")
        self.viewer_runtime.start()
        self._refresh_3d()

    def _show_split(self) -> None:
        """Show 2D canvas and 3D viewer side-by-side in split-screen mode."""
        # Configure grid for true 50/50 split with uniform sizing
        self.workspace_content.grid_columnconfigure(0, weight=1, minsize=0, uniform="split")
        self.workspace_content.grid_columnconfigure(1, weight=1, minsize=0, uniform="split")
        
        # Show both containers
        self.canvas_container.grid(row=0, column=0, sticky="nsew", padx=(1, 0), pady=1)
        self.viewer_container.grid(row=0, column=1, sticky="nsew", padx=(1, 1), pady=1)
        
        self._workspace_mode = "split"
        self._set_workspace_tab_style("split")
        
        # Start viewer if not already running
        self.viewer_runtime.start()
        self._refresh_3d()
        
        # Force geometry update, then redraw grid
        self.workspace_content.update_idletasks()
        self.root.after_idle(self.view.schedule_grid_redraw)

    def _on_project_mutation(self) -> None:
        if hasattr(self, "parity_toolbar"):
            self.parity_toolbar.refresh()
        if hasattr(self, "autosaver"):
            self.autosaver.schedule()
        self._schedule_detected_room_refresh()
        self._schedule_viewer_refresh()

    def _schedule_detected_room_refresh(self) -> None:
        """Debounced re-detection of rooms from the live canvas, so enclosures
        drawn with the Line/Polygon tool appear as real rooms as the user draws."""
        if self._detect_after_id is not None:
            try:
                self.root.after_cancel(self._detect_after_id)
            except Exception:
                pass
            self._detect_after_id = None
        if not self._app_alive:
            return
        self._detect_after_id = self.root.after(150, self._run_detected_room_refresh)

    def _run_detected_room_refresh(self) -> None:
        self._detect_after_id = None
        if not self._app_alive:
            return
        try:
            self.serializer.refresh_detected_room_overlay()
        except Exception as exc:
            print(f"[app] detected room refresh failed: {exc}")

    def _schedule_viewer_refresh(self) -> None:
        if self._viewer_after_id is not None:
            try:
                self.root.after_cancel(self._viewer_after_id)
            except Exception:
                pass
            self._viewer_after_id = None
        # Refresh for both viewer and split modes
        if self._workspace_mode not in ("viewer", "split") or not self._app_alive:
            return
        self._viewer_after_id = self.root.after(250, self._run_debounced_viewer_refresh)

    def _run_debounced_viewer_refresh(self) -> None:
        self._viewer_after_id = None
        if self._workspace_mode in ("viewer", "split") and self._app_alive:
            self._send_viewer_layout()

    def _send_viewer_layout(self) -> None:
        try:
            self.viewer_runtime.send_layout(self.serializer.serialize_layout())
        except Exception as exc:
            self.viewer_runtime.send_host_error(f"Could not serialize the current plan: {exc}")

    def _refresh_3d(self) -> None:
        """Explicit refresh: bypass the debounce and send immediately."""
        if self._viewer_after_id is not None:
            try:
                self.root.after_cancel(self._viewer_after_id)
            except Exception:
                pass
            self._viewer_after_id = None
        self._send_viewer_layout()

    def _setup_toolbar(self) -> None:
        setup_toolbar(
            self.main_frame,
            self.model,
            self.tools,
            self.controller,
            self.view,
            self.actions,
            top_toolbar=getattr(self, "top_toolbar", None),
            on_local_save=lambda: self.autosaver.save_now(),
            on_local_load_last=self._load_local_last,
            on_local_load_file=self._load_local_from_file,
        )

    def _on_closing(self) -> None:
        """Cleanup all background tasks before closing the window."""
        try:
            self.actions.post_mutation_callback = None
            if self._viewer_after_id is not None:
                try:
                    self.root.after_cancel(self._viewer_after_id)
                except Exception:
                    pass
                self._viewer_after_id = None
            if getattr(self, "_detect_after_id", None) is not None:
                try:
                    self.root.after_cancel(self._detect_after_id)
                except Exception:
                    pass
                self._detect_after_id = None
            if hasattr(self, "viewer_runtime"):
                self.viewer_runtime.close()

            # Stop local autosave
            if hasattr(self, 'autosaver'):
                self.autosaver.unwrap_action_logger()
                # Cancel heartbeat if running
                if hasattr(self.autosaver, '_hb_after_id') and self.autosaver._hb_after_id:
                    try:
                        self.root.after_cancel(self.autosaver._hb_after_id)
                    except Exception:
                        pass
                    self.autosaver._hb_after_id = None
            
            # Cancel door recut callback if running
            if hasattr(self.tools, '_door_recut_after_id') and self.tools._door_recut_after_id:
                try:
                    self.root.after_cancel(self.tools._door_recut_after_id)
                except Exception:
                    pass
                self.tools._door_recut_after_id = None
            
            # Cancel grid redraw callback if running
            if hasattr(self.view, '_grid_redraw_after_id') and self.view._grid_redraw_after_id:
                try:
                    self.view.canvas.after_cancel(self.view._grid_redraw_after_id)
                except Exception:
                    pass
                self.view._grid_redraw_after_id = None
        except Exception as e:
            print(f"[MiniAutoCAD] Cleanup error: {e}")
        finally:
            self._app_alive = False
            # Destroy the window
            try:
                self.root.destroy()
            except Exception:
                pass

    def _on_root_destroy(self, _event=None) -> None:
        self._app_alive = False

    def _is_app_alive(self) -> bool:
        try:
            return self._app_alive and self.root.winfo_exists()
        except Exception:
            return False

    def _report_callback_exception(self, exc, val, tb) -> None:
        if not self._is_app_alive():
            return
        try:
            err_text = str(val)
            if "application has been destroyed" in err_text or "invalid command name" in err_text:
                return
        except Exception:
            pass
        try:
            import traceback

            traceback.print_exception(exc, val, tb)
        except Exception:
            pass
        _append_crash_log("TK CALLBACK", exc, val, tb)

    def _bgerror(self, msg) -> None:
        if not self._is_app_alive():
            return
        try:
            err_text = str(msg)
            if "application has been destroyed" in err_text or "invalid command name" in err_text:
                return
        except Exception:
            pass
        try:
            print(f"[MiniAutoCAD][bgerror] {msg}")
        except Exception:
            pass

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    launch_app()
