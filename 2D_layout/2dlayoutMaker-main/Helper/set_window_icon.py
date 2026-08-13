import ctypes
import os
import sys
import tkinter as tk
from tkinter import PhotoImage

from app_paths import get_asset_root

# Stable AppUserModelID for Windows taskbar grouping / icon
# NOTE: Icon image for the taskbar still comes from the EXE's resources,
# but having a fixed ID avoids random grouping and improves pinning behavior.
APP_ID = "CallAstro.MiniAutoCAD"

def _inherit_icon_from_parent(root) -> bool:
    """
    Best-effort: inherit icon from parent/master window.

    This is important for Toplevel dialogs where file-based icon lookup may fail
    (for example when running as an encrypted component without local assets).
    """
    try:
        parent = getattr(root, "master", None)
        if not parent:
            return False
        top = parent.winfo_toplevel() if hasattr(parent, "winfo_toplevel") else parent
        icon = getattr(top, "_window_icon_ref", None)
        if not icon:
            return False
        try:
            setattr(root, "_window_icon_ref", icon)
        except Exception:
            pass
        try:
            root.iconphoto(False, icon)
        except Exception:
            return False
        return True
    except Exception:
        return False


def set_window_icon(root, icon_path=None):
    """
    Sets the window icon for both the title bar and the taskbar across platforms.
    
    Parameters:
    root (tk.Tk or tk.Toplevel): The Tkinter window instance.
    icon_path (str): Path to the icon file (.png or .ico). If None, uses default paths.
    """
    # Default icon paths to try (cross-platform)
    env_home = os.environ.get("VASTUAPP_HOME") or ""
    try:
        is_frozen = bool(getattr(sys, "frozen", False))
        exe_dir = os.path.dirname(sys.executable) if is_frozen else ""
    except Exception:
        exe_dir = ""
    meipass = getattr(sys, "_MEIPASS", "") if hasattr(sys, "_MEIPASS") else ""

    # Project root (dev) is the parent of Helper.
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        dev_project_root = os.path.normpath(os.path.join(here, os.pardir))
    except Exception:
        dev_project_root = ""

    def _candidates(base: str) -> list[str]:
        if not base:
            return []
        return [
            # Centralized layout first; old locations remain fallback-compatible.
            os.path.join(base, "assets", "branding", "icon.ico"),
            os.path.join(base, "assets", "branding", "welcome_image.png"),
            os.path.join(base, "assets", "icon.ico"),
            os.path.join(base, "Assets", "icon.ico"),
            os.path.join(base, "assets", "welcome_image.png"),
            os.path.join(base, "Assets", "welcome_image.png"),
            os.path.join(base, "welcome_image.png"),
            os.path.join(base, "welcome_image.ico"),
            os.path.join(base, "icon.ico"),
        ]

    # Build search list. On Windows, check ICO first to avoid the default Tk "leaf" icon.
    branding_dir = os.path.join(get_asset_root(), "branding")
    central_paths = [
        os.path.join(branding_dir, "icon.ico"),
        os.path.join(branding_dir, "welcome_image.png"),
    ]
    if icon_path is None:
        if sys.platform == "win32":
            default_paths = central_paths + [
                os.path.join("assets", "branding", "icon.ico"),
                os.path.join("assets", "branding", "welcome_image.png"),
                os.path.join("..", "welcome_image.png"),
            ]
        else:
            default_paths = list(reversed(central_paths)) + [
                os.path.join("assets", "branding", "welcome_image.png"),
                os.path.join("..", "welcome_image.png"),
            ]
        default_paths = default_paths + _candidates(dev_project_root) + _candidates(env_home) + _candidates(exe_dir) + _candidates(meipass)
    else:
        # If a specific path is provided, try it first, then fallbacks
        default_paths = [icon_path]
        if sys.platform == "win32":
            default_paths += [
                os.path.join(branding_dir, "icon.ico"),
                os.path.join(branding_dir, "welcome_image.png"),
                "welcome_image.ico",
                "icon.ico",
                "welcome_image.png",
            ]
        else:
            default_paths += [
                os.path.join(branding_dir, "welcome_image.png"),
                "welcome_image.png",
                "icon.ico",
            ]
        default_paths = default_paths + _candidates(dev_project_root) + _candidates(env_home) + _candidates(exe_dir) + _candidates(meipass)
    
    # Find the first existing icon file
    working_icon_path = None
    for path in default_paths:
        if os.path.exists(path):
            working_icon_path = path
            break
    
    if not working_icon_path:
        # If running as frozen EXE and we didn't find any icon file,
        # DO NOT override the icon – let Windows use the EXE's embedded icon
        # for both title bar and taskbar.
        try:
            is_frozen = bool(getattr(sys, "frozen", False))
        except Exception:
            is_frozen = False

        if is_frozen:
            # Best effort: for dialogs, try inheriting from the main window.
            _inherit_icon_from_parent(root)
            return

        # Non-frozen (dev) mode: create a simple default icon programmatically
        # to avoid the ugly Tk leaf icon while developing.
        try:
            from PIL import Image, ImageDraw, ImageTk
            # Create a simple 32x32 icon with a square/box design
            icon_img = Image.new('RGBA', (32, 32), (0, 0, 0, 0))
            draw = ImageDraw.Draw(icon_img)
            # Draw a simple box/square icon
            draw.rectangle([4, 4, 28, 28], fill=(70, 130, 180), outline=(50, 100, 150), width=2)
            # Convert to PhotoImage and set as icon
            icon_photo = ImageTk.PhotoImage(icon_img)
            setattr(root, "_window_icon_ref", icon_photo)
            root.iconphoto(False, icon_photo)
            print("Created default programmatic icon to avoid tkinter leaf icon (dev mode).")
            return
        except Exception as e:
            print(f"Warning: No icon file found and could not create default icon: {e}")
            return
    
    try:
        # Windows: prefer .ico + iconbitmap for reliable titlebar icon.
        if working_icon_path.lower().endswith(".ico") and sys.platform == "win32":
            try:
                root.iconbitmap(working_icon_path)
                print(f"Successfully set window icon: {working_icon_path}")
                return
            except Exception as e:
                print(f"Error setting .ico iconbitmap from {working_icon_path}: {e}")
                # continue to PNG/iconphoto fallback

        # PNG fallback (works cross-platform; may not change Windows titlebar in some themes)
        icon = PhotoImage(master=root, file=working_icon_path)
        # Persist reference on root to prevent garbage collection
        setattr(root, "_window_icon_ref", icon)
        root.iconphoto(False, icon)

        print(f"Successfully set window icon: {working_icon_path}")
    except Exception as e:
        print(f"Error loading window icon from {working_icon_path}: {e}")
        # If file-based icon failed, try parent inheritance as a fallback.
        try:
            _inherit_icon_from_parent(root)
        except Exception:
            pass

    # Platform-specific taskbar/dock icon fixes
    if sys.platform == "win32":
        # Fix taskbar grouping / pinning on Windows
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        except Exception as e:
            print(f"Error setting Windows taskbar AppUserModelID: {e}")
    elif sys.platform == "darwin":
        # macOS dock icon handling and taskbar restoration
        try:
            # On macOS, the dock icon is typically handled by the app bundle
            # For command-line apps, we can set the window icon which may affect dock
            
            # Set up proper window restoration from dock
            if hasattr(root, 'createcommand'):
                root.createcommand('::tk::mac::ReopenApplication', lambda: _restore_window_macos(root))
            
            # Set proper window attributes for better taskbar behavior
            if hasattr(root, 'wm_attributes'):
                try:
                    root.wm_attributes('-modified', False)
                except Exception:
                    pass  # Some attributes may not be available
                    
        except Exception as e:
            print(f"Error setting macOS dock icon: {e}")
    # Linux typically handles this automatically via window managers

def _restore_window_macos(root):
    """Helper function to properly restore window on macOS when clicked from dock"""
    try:
        # Check current window state and restore accordingly
        current_state = root.state()
        
        if current_state == 'iconic':
            root.deiconify()
        elif current_state == 'withdrawn':
            root.deiconify()
        
        # Bring window to front
        root.lift()
        root.focus_force()
        
        # Ensure window is visible and on top temporarily
        root.attributes('-topmost', True)
        root.after(100, lambda: root.attributes('-topmost', False))
        
        print("macOS window restored from dock")
        
    except Exception as e:
        print(f"Error in macOS window restore: {e}")