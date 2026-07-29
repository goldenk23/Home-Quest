
import platform
import tkinter as tk

# Platform detection
_IS_MACOS = platform.system() == "Darwin"
_IS_WINDOWS = platform.system() == "Windows"

# Platform-specific imports
if _IS_MACOS:
    # For macOS: Direct import of customtkinter
    try:
        import customtkinter as ctk
    except Exception:  # pragma: no cover
        ctk = None  # type: ignore
elif _IS_WINDOWS:
    # For Windows: Use ctk_global approach with scaling
    try:
        import customtkinter as ctk  # re-exported below
    except Exception:  # pragma: no cover
        ctk = None  # type: ignore
else:
    # For other platforms: Direct import as fallback
    try:
        import customtkinter as ctk
    except Exception:  # pragma: no cover
        ctk = None  # type: ignore

def _map_tk_scaling_to_logical(tk_scaling):
    """Map fractional Tk scaling to standard Windows DPI scaling."""
    if tk_scaling < 1.1:
        return 1.0   # 100%
    elif tk_scaling < 1.4:
        return 1.25  # 125%
    elif tk_scaling < 1.7:
        return 1.5   # 150%
    else:
        return 2.0   # 200% or higher

def _enable_ctk_auto_scaling():
    """Automatically set CustomTkinter scaling according to system DPI and harden tracker."""
    # Only apply Windows-specific scaling on Windows
    if not ctk or not _IS_WINDOWS:
        return

    # Detect system DPI scaling
    try:
        root = tk.Tk()
        tk_scaling = float(root.tk.call('tk', 'scaling'))
        print("tk_scaling from root:", tk_scaling)
        root.destroy()
    except Exception:
        print("Exception in _enable_ctk_auto_scaling")
        tk_scaling = 1.0  # fallback

    # Map to logical Windows scaling
    logical_scaling = _map_tk_scaling_to_logical(tk_scaling)
    print("logical_scaling from root:", logical_scaling)

    # Apply scaling globally
    try:
        ctk.set_window_scaling(logical_scaling)
    except Exception:
        pass

    try:
        ctk.set_widget_scaling(logical_scaling)
    except Exception:
        pass

    # Harden scaling tracker against Tk roots
    try:
        from customtkinter.windows.widgets.scaling.scaling_tracker import ScalingTracker  # type: ignore

        original_check = getattr(ScalingTracker, "check_dpi_scaling", None)
        if callable(original_check):
            def _safe_check(*args, **kwargs):
                try:
                    return original_check(*args, **kwargs)
                except Exception:
                    return None

            setattr(ScalingTracker, "check_dpi_scaling", _safe_check)
    except Exception:
        pass

def patch_tk_root(root):
    """Make a tk.Tk or tk.Toplevel root CTk-friendly for scaling tracker."""
    try:
        if not hasattr(root, "block_update_dimensions_event"):
            setattr(root, "block_update_dimensions_event", lambda *a, **k: None)
        if not hasattr(root, "unblock_update_dimensions_event"):
            setattr(root, "unblock_update_dimensions_event", lambda *a, **k: None)

        # Apply logical scaling to plain Tk roots only on Windows
        if _IS_WINDOWS:
            try:
                tk_scaling = float(root.tk.call('tk', 'scaling'))
                print("tk_scaling from patch_tk_root:", tk_scaling)
            except Exception:
                print("Exception in patch_tk_root")
                tk_scaling = 1.0

            logical_scaling = _map_tk_scaling_to_logical(tk_scaling)
            print("logical_scaling from patch_tk_root:", logical_scaling)
            root.tk.call('tk', 'scaling', logical_scaling)
    except Exception:
        pass
    return root

# Keep native CustomTkinter defaults consistent with the app's explicit dark glass palette.
try:
    if ctk:
        ctk.set_appearance_mode("Dark")
except Exception:
    pass

# Execute once on import so every module benefits
try:
    _enable_ctk_auto_scaling()
except Exception:
    pass

# Re-export ctk for "from Helper.ctk_global import ctk"
__all__ = ["ctk", "patch_tk_root"]
