import threading
import time
import tkinter as tk
from tkinter import messagebox
import sys
import platform

# Try to import ttkbootstrap, fall back to standard ttk if not available
try:
    import ttkbootstrap as ttk
    TTKBOOTSTRAP_AVAILABLE = True
    print("[showMessage] Using ttkbootstrap for enhanced UI")
except ImportError:
    import tkinter.ttk as ttk
    TTKBOOTSTRAP_AVAILABLE = False
    print("[showMessage] ttkbootstrap not available, using standard ttk")
    print("[showMessage] ttkbootstrap not available, using standard ttk")

# Platform-specific imports
if sys.platform == "win32":
    import ctypes
    myappid = 'callastro.vastuapp.'  # Change as needed
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass  # Ignore if this fails

# -----------------------------------------------------------------------------
# Cross-platform constants and utilities
# -----------------------------------------------------------------------------
# Win32 constants (used only on Windows for fallback dialog icon handling)
if sys.platform == "win32":
    try:
        WM_SETICON      = 0x0080
        ICON_SMALL      = 0
        ICON_BIG        = 1
        IMAGE_ICON      = 1
        LR_LOADFROMFILE = 0x00000010
        
        # For setting the class icon on 64-bit vs 32-bit Windows:
        GCL_HICON       = -14
        GCL_HICONSM     = -34
        
        user32 = ctypes.windll.user32
        try:
            SetClassLongPtr = user32.SetClassLongPtrW
        except AttributeError:
            SetClassLongPtr = user32.SetClassLongW
    except Exception:
        # If ctypes fails, disable Windows-specific features
        user32 = None
        SetClassLongPtr = None
else:
    # Non-Windows platforms - set to None
    user32 = None
    SetClassLongPtr = None

# Cache for message configurations to avoid repeated dictionary lookups
_MESSAGE_CONFIGS = {
    "info": {
        "icon": "ℹ️",
        "color": "#3498db",
        "primary_style": "info" if TTKBOOTSTRAP_AVAILABLE else "",
        "secondary_style": "secondary" if TTKBOOTSTRAP_AVAILABLE else "",
        "accent_style": "info.TFrame" if TTKBOOTSTRAP_AVAILABLE else ""
    },
    "error": {
        "icon": "🚫",
        "color": "#e74c3c",
        "primary_style": "danger" if TTKBOOTSTRAP_AVAILABLE else "",
        "secondary_style": "secondary" if TTKBOOTSTRAP_AVAILABLE else "",
        "accent_style": "danger.TFrame" if TTKBOOTSTRAP_AVAILABLE else ""
    },
    "warning": {
        "icon": "⚠️",
        "color": "#f39c12",
        "primary_style": "warning" if TTKBOOTSTRAP_AVAILABLE else "",
        "secondary_style": "secondary" if TTKBOOTSTRAP_AVAILABLE else "",
        "accent_style": "warning.TFrame" if TTKBOOTSTRAP_AVAILABLE else ""
    },
    "yesno": {
        "icon": "❓",
        "color": "#9b59b6",
        "primary_style": "primary" if TTKBOOTSTRAP_AVAILABLE else "",
        "secondary_style": "secondary" if TTKBOOTSTRAP_AVAILABLE else "",
        "accent_style": "primary.TFrame" if TTKBOOTSTRAP_AVAILABLE else ""
    },
    "retrycancel": {
        "icon": "🔄",
        "color": "#34495e",
        "primary_style": "primary" if TTKBOOTSTRAP_AVAILABLE else "",
        "secondary_style": "secondary" if TTKBOOTSTRAP_AVAILABLE else "",
        "accent_style": "secondary.TFrame" if TTKBOOTSTRAP_AVAILABLE else ""
    }
}

def _create_cross_platform_button(parent, text, command, style, width=14):
    """Create a button with cross-platform styling"""
    if TTKBOOTSTRAP_AVAILABLE and style:
        try:
            return ttk.Button(
                parent,
                text=text,
                command=command,
                bootstyle=style,
                width=width,
                cursor="hand2"
            )
        except Exception:
            pass
    
    # Fallback to standard button
    return ttk.Button(
        parent,
        text=text,
        command=command,
        width=width,
        cursor="hand2"
    )

def _get_system_font(size=11, weight="normal"):
    """
    Get the best available system font for cross-platform compatibility.
    """
    if sys.platform == "win32":
        return ("Segoe UI", size, weight) if weight != "normal" else ("Segoe UI", size)
    elif sys.platform == "darwin":
        return ("SF Pro Text", size, weight) if weight != "normal" else ("SF Pro Text", size)
    else:  # Linux and others
        return ("DejaVu Sans", size, weight) if weight != "normal" else ("DejaVu Sans", size)

# Global variables for preloaded components
_PRELOADED = False
_WARMUP_ROOT = None

def _preload_dialog_components():
    """
    Preload and warm up all dialog components to eliminate first-time delays.
    This creates a hidden dialog with all widget types to initialize the rendering pipeline.
    MUST be called from the main thread only.
    """
    global _PRELOADED, _WARMUP_ROOT
    
    if _PRELOADED:
        return
    
    try:
        # Only proceed if we're in the main thread
        if threading.current_thread() != threading.main_thread():
            return
            
        # Create a hidden root window for preloading
        _WARMUP_ROOT = tk.Tk()
        _WARMUP_ROOT.withdraw()  # Hide it immediately
        _WARMUP_ROOT.attributes('-alpha', 0.0)  # Make it transparent
        
        # Create a hidden dialog with all widget types to warm up the system
        warmup_dialog = tk.Toplevel(_WARMUP_ROOT)
        warmup_dialog.withdraw()  # Hide it
        warmup_dialog.attributes('-alpha', 0.0)
        warmup_dialog.configure(bg='#f8f9fa')
        
        # Pre-create all widget types used in dialogs
        main_container = ttk.Frame(warmup_dialog, padding=0)
        header_frame = ttk.Frame(main_container, padding=(0, 0, 0, 3))
        
        # Preload all accent styles
        for config in _MESSAGE_CONFIGS.values():
            accent_line = ttk.Frame(header_frame, height=3)
            try:
                accent_line.configure(style=config['accent_style'])
            except:
                pass  # Style might not exist yet
        
        content_frame = ttk.Frame(main_container, padding=(30, 0, 30, 25))
        message_container = ttk.Frame(content_frame)
        icon_frame = ttk.Frame(message_container)
        
        # Preload fonts and emoji rendering
        for config in _MESSAGE_CONFIGS.values():
            icon_label = ttk.Label(
                icon_frame,
                text=config['icon'],
                font=_get_system_font(24),
                foreground=config['color']
            )
        
        # Preload message label with long text to initialize text rendering
        message_label = ttk.Label(
            message_container,
            text="Preloading message dialog components for faster rendering...",
            font=_get_system_font(11),
            wraplength=400,
            justify="left",
            foreground="#2c3e50"
        )
        
        separator = ttk.Separator(content_frame, orient="horizontal")
        button_frame = ttk.Frame(content_frame)
        
        # Preload all button styles
        button_styles = ["info", "danger", "warning", "primary", "secondary"]
        for style in button_styles:
            try:
                test_btn = ttk.Button(
                    button_frame,
                    text="Test",
                    bootstyle=style,
                    width=14,
                    cursor="hand2"
                )
            except:
                pass  # Style might not be available
        
        # Pack everything to trigger widget creation
        main_container.pack()
        header_frame.pack()
        content_frame.pack()
        message_container.pack()
        icon_frame.pack()
        message_label.pack()
        separator.pack()
        button_frame.pack()
        
        # Force update to complete initialization
        warmup_dialog.update_idletasks()
        
        # Clean up the warmup dialog
        warmup_dialog.destroy()
        
        _PRELOADED = True
        
    except Exception as e:
        # If preloading fails, don't crash - just continue without preloading
        _PRELOADED = True  # Mark as done to avoid retrying


def _ensure_preloaded():
    """Ensure components are preloaded before creating dialogs (main thread only)"""
    global _PRELOADED
    try:
        if not _PRELOADED and threading.current_thread() == threading.main_thread():
            print("[showMessage] Preloading dialog components...")
            _preload_dialog_components()
            print("[showMessage] Dialog components preloaded successfully")
    except Exception as e:
        print(f"[showMessage] Warning: Could not preload components: {e}")
        # Mark as preloaded to avoid retrying
        _PRELOADED = True


def _set_msgbox_icon_async(window_title, icon_path):
    """
    If our custom dialog fails and we fall back to the standard tkinter.messagebox,
    this function will attempt to set the icon on Windows. On other platforms, it does nothing.
    """
    # Only works on Windows with proper ctypes support
    if sys.platform != "win32" or user32 is None:
        return
    
    # Check if all required Windows constants are available
    try:
        # Verify all constants exist before proceeding
        required_constants = [WM_SETICON, ICON_SMALL, ICON_BIG, IMAGE_ICON, LR_LOADFROMFILE, GCL_HICON, GCL_HICONSM]
        if not all(const is not None for const in [WM_SETICON, ICON_SMALL, ICON_BIG, IMAGE_ICON, LR_LOADFROMFILE, GCL_HICON, GCL_HICONSM]):
            return
    except NameError:
        # Constants not defined, skip icon setting
        return
        
    def _worker():
        try:
            import ctypes
            # Give the native dialog a moment to exist
            time.sleep(0.1)
            for _ in range(10):
                hwnd = user32.FindWindowW("#32770", window_title)
                if hwnd:
                    hicon = user32.LoadImageW(
                        None, icon_path, IMAGE_ICON, 0, 0, LR_LOADFROMFILE
                    )
                    if not hicon:
                        return
                    # Swap both the small and big icons
                    user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, ctypes.c_void_p(hicon))
                    user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, ctypes.c_void_p(hicon))
                    # Also swap the class icons so taskbar/titlebar updates
                    if SetClassLongPtr:
                        SetClassLongPtr(hwnd, GCL_HICON, ctypes.c_void_p(hicon))
                        SetClassLongPtr(hwnd, GCL_HICONSM, ctypes.c_void_p(hicon))
                    return
                time.sleep(0.02)
        except Exception:
            # Silently ignore any errors on icon setting
            pass
    
    # Actually start the worker thread (this was missing!)
    threading.Thread(target=_worker, daemon=True).start()


def _estimate_text_width(text, font_size=11):
    """
    Fast text width estimation without creating temporary widgets.
    Uses average character width approximation.
    """
    # Average character width in pixels for common fonts at size 11
    avg_char_width = font_size * 0.6
    lines = text.split('\n')
    max_line_length = max(len(line) for line in lines) if lines else 0
    return int(max_line_length * avg_char_width)


# -----------------------------------------------------------------------------
# CORE: Create a custom, "modern" dialog - OPTIMIZED VERSION
# -----------------------------------------------------------------------------
def _create_custom_dialog(message_type, title, message, errorCode="", parent=None, 
                         auto_close=True, auto_close_timeout=30, **options):
    """
    Optimized version that creates dialogs faster by:
    1) Using text width estimation instead of temporary widgets
    2) Minimizing update_idletasks calls
    3) Removing/simplifying animations
    4) Streamlined widget creation
    5) On-demand preloading for faster first-time rendering (main thread only)
    """
    
    try:
        print(f"[_create_custom_dialog] Starting creation for type: {message_type}")
        
        # Ensure all components are preloaded for fast rendering (main thread only)
        _ensure_preloaded()

        # 1) Determine parent
        if parent is None:
            try:
                parent = tk._default_root
                print(f"[_create_custom_dialog] Using default root: {parent}")
            except Exception:
                if _WARMUP_ROOT and _WARMUP_ROOT.winfo_exists():
                    parent = _WARMUP_ROOT
                    print(f"[_create_custom_dialog] Using warmup root: {parent}")
                else:
                    parent = tk.Tk()
                    parent.withdraw()
                    print(f"[_create_custom_dialog] Created new root: {parent}")

        print(f"[_create_custom_dialog] Parent determined: {parent}")
        
        # 2) Create the Toplevel window
        dialog = tk.Toplevel(parent)
        print("[_create_custom_dialog] Toplevel window created")
        dialog.title(title)
        dialog.resizable(False, False)
        # Keep dialog logically attached to its parent so macOS (and other OS) treat
        # it as a child of the main VastuCraft Pro window instead of a separate full‑screen window.
        try:
            dialog.transient(parent)
        except Exception:
            pass
        dialog.grab_set()
        try:
            dialog.attributes('-topmost', True)
        except Exception:
            pass
        dialog.configure(bg='#f8f9fa')
        # On macOS, hide the native minimize/zoom buttons by removing the title bar;
        # users interact via the dialog buttons (OK / Yes / No / Close) instead.
        try:
            if platform.system() == "Darwin":
                dialog.overrideredirect(True)
        except Exception:
            pass
        print("[_create_custom_dialog] Dialog window configured")

        # Try to set a custom window icon if you have one (optional)
        try:
            from Helper.set_window_icon import set_window_icon
            set_window_icon(dialog)
            print("[_create_custom_dialog] Window icon set successfully")
        except ImportError:
            print("[_create_custom_dialog] set_window_icon module not found, skipping icon")
        except Exception as icon_error:
            print(f"[_create_custom_dialog] Could not set window icon: {icon_error}")
            # Don't let icon errors crash the dialog

        result = [None]

        # == STEP 1: Fast text width estimation ==
        estimated_width = _estimate_text_width(message)
        print(f"[_create_custom_dialog] Estimated width: {estimated_width}")
        
        # Clamp the width between some min and max
        min_width = 500
        max_width = 1100
        padding_width = 180  # accounts for icon + left/right margins

        base_width = min(max(estimated_width + padding_width, min_width), max_width)

        # == STEP 2: Get cached configuration ==
        config = _MESSAGE_CONFIGS.get(message_type, _MESSAGE_CONFIGS["info"])

        # == STEP 3: Build UI in one go to minimize redraws ==
        main_container = ttk.Frame(dialog, padding=0)
        
        # 3a) Accent line at the top with title + close button
        header_frame = ttk.Frame(main_container, padding=(0, 0, 0, 3))
        accent_line = ttk.Frame(header_frame, height=3)
        try:
            accent_line.configure(style=config['accent_style'])
        except Exception:
            pass  # Style might not exist
        
        # Add title label since title bar is removed
        title_label = ttk.Label(
            header_frame,
            text=title,
            font=_get_system_font(13, "bold"),
            foreground="#111827",
            background="#f3f4f6",
        )
        close_btn = ttk.Button(
            header_frame,
            text="✕",
            width=3,
            command=lambda: None,  # actual command wired below after close handler is defined
        )

        # 3b) Icon + message area
        content_frame = ttk.Frame(main_container, padding=(30, 0, 30, 25))
        message_container = ttk.Frame(content_frame)

        # Left: the emoji/icon
        icon_frame = ttk.Frame(message_container)
        icon_label = ttk.Label(
            icon_frame,
            text=config['icon'],
            font=_get_system_font(24),
            foreground=config['color']
        )

        # Right: the actual message text
        wrap_len = base_width - 120
        message_label = ttk.Label(
            message_container,
            text=message,
            font=_get_system_font(11),
            wraplength=wrap_len,
            justify="left",
            foreground="#2c3e50"
        )

        # 3c) Separator above the buttons
        separator = ttk.Separator(content_frame, orient="horizontal")

        # 3d) Button container
        button_frame = ttk.Frame(content_frame)

        # 3e) Countdown label for auto-close feature (only if auto_close is enabled)
        countdown_frame = ttk.Frame(content_frame)
        countdown_label = None
        if auto_close:
            countdown_label = ttk.Label(
                countdown_frame,
                text=f"Auto-close in {auto_close_timeout} seconds",
                font=_get_system_font(9),
                foreground="#7f8c8d"
            )
            countdown_label.pack()

        # == STEP 4: Pack everything at once to minimize redraws ==
        main_container.pack(fill="both", expand=True)
        header_frame.configure(style=config.get("accent_style", ""))
        header_frame.pack(fill="x", padx=16, pady=(16, 0))
        accent_line.pack(fill="x", pady=(0, 6))
        # left-align title, right-align close button for custom header bar
        title_label.pack(side="left", pady=(4, 8))
        close_btn.pack(side="right", pady=(4, 8))
        content_frame.pack(fill="both", expand=True)
        message_container.pack(fill="both", expand=True, pady=(0, 25))
        icon_frame.pack(side="left", padx=(0, 20), anchor="n", pady=(5, 0))
        icon_label.pack()
        message_label.pack(side="left", fill="both", expand=True, anchor="n")
        separator.pack(fill="x", pady=(0, 20))
        if auto_close:
            countdown_frame.pack(fill="x", pady=(0, 10))
        button_frame.pack(fill="x")

        # 3e) Handle the window close event
        def on_window_close():
            try:
                # Set a default result if none was set
                if result[0] is None:
                    result[0] = False  # Default to False/Cancel
                dialog.attributes('-topmost', False)
                dialog.grab_release()
            except tk.TclError:
                pass
            try:
                dialog.destroy()
            except tk.TclError:
                pass

        dialog.protocol("WM_DELETE_WINDOW", on_window_close)

        # 3f) Auto-close timer setup (configurable timeout)
        auto_close_timer = [None]  # Use list to allow modification in nested functions
        countdown_timer = [None]
        countdown_remaining = [auto_close_timeout]  # Configurable countdown
        
        def update_countdown():
            """Update the countdown display"""
            try:
                if countdown_remaining[0] > 0 and dialog.winfo_exists() and countdown_label:
                    countdown_label.config(text=f"Auto-close in {countdown_remaining[0]} seconds")
                    countdown_remaining[0] -= 1
                    countdown_timer[0] = dialog.after(1000, update_countdown)  # Update every second
                elif countdown_remaining[0] <= 0 and dialog.winfo_exists() and countdown_label:
                    countdown_label.config(text="Closing...")
            except Exception as e:
                print(f"[_create_custom_dialog] Countdown update error: {e}")
        
        def auto_close_dialog():
            """Automatically close the dialog after timeout"""
            try:
                if result[0] is None and dialog.winfo_exists():
                    print(f"[_create_custom_dialog] Auto-closing dialog after {auto_close_timeout} seconds")
                    # For single button dialogs (info, warning, error), click OK
                    if message_type in ["error", "warning", "info"]:
                        result[0] = True
                    # For choice dialogs, default to the safer/cancel option
                    elif message_type == "yesno":
                        result[0] = False  # Default to "No"
                    elif message_type == "retrycancel":
                        result[0] = False  # Default to "Cancel"
                    else:
                        result[0] = True  # Fallback to True
                    
                    # Close the dialog
                    on_window_close()
            except Exception as e:
                print(f"[_create_custom_dialog] Auto-close error: {e}")
        
        # Only setup auto-close if enabled
        if auto_close:
            # Start the countdown display
            update_countdown()
            
            # Schedule auto-close after the specified timeout
            auto_close_timer[0] = dialog.after(auto_close_timeout * 1000, auto_close_dialog)
        
        # Modified close function to cancel the timers
        original_on_window_close = on_window_close
        def on_window_close_with_timer_cancel():
            # Cancel both timers if dialog is closed manually
            if auto_close_timer[0] is not None:
                try:
                    dialog.after_cancel(auto_close_timer[0])
                    auto_close_timer[0] = None
                    print("[_create_custom_dialog] Auto-close timer cancelled - user closed dialog")
                except Exception as timer_error:
                    print(f"[_create_custom_dialog] Auto-close timer cancel error: {timer_error}")
            
            if countdown_timer[0] is not None:
                try:
                    dialog.after_cancel(countdown_timer[0])
                    countdown_timer[0] = None
                    print("[_create_custom_dialog] Countdown timer cancelled - user closed dialog")
                except Exception as timer_error:
                    print(f"[_create_custom_dialog] Countdown timer cancel error: {timer_error}")
            
            # Call the original close function
            original_on_window_close()
        
        # Wire header close button and WM protocol to the same handler
        try:
            close_btn.configure(command=on_window_close_with_timer_cancel)
        except Exception:
            pass
        dialog.protocol("WM_DELETE_WINDOW", on_window_close_with_timer_cancel)
        
        def _on_unmap(_event=None):
            """
            If the enhanced dialog window is minimized/hidden, close it cleanly
            so the main canvas is never left blocked behind an invisible modal.
            """
            try:
                if str(dialog.state()) == "iconic":
                    on_window_close_with_timer_cancel()
            except Exception:
                on_window_close_with_timer_cancel()
        
        dialog.bind("<Unmap>", _on_unmap)
        
        # 3g) Create buttons based on message type
        print(f"[_create_custom_dialog] Creating buttons for message type: {message_type}")
        _create_enhanced_buttons(dialog, button_frame, message_type, config, result, on_window_close_with_timer_cancel, auto_close_timer, countdown_timer)
        print(f"[_create_custom_dialog] Buttons created successfully")

        # == STEP 5: Single update and immediate geometry setting ==
        dialog.update_idletasks()
        real_height = dialog.winfo_reqheight()

        # Center over parent window when possible so dialogs stay visually attached
        # to the main VastuCraft Pro window (especially on macOS); otherwise fall back
        # to screen center with (base_width × real_height).
        try:
            px = parent.winfo_x()
            py = parent.winfo_y()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            if pw > 0 and ph > 0:
                x = px + max((pw - base_width) // 2, 0)
                y = py + max((ph - real_height) // 2, 0)
            else:
                raise RuntimeError("Parent size not ready")
        except Exception:
            screen_w = dialog.winfo_screenwidth()
            screen_h = dialog.winfo_screenheight()
            x = (screen_w // 2) - (base_width // 2)
            y = (screen_h // 2) - (real_height // 2)

        dialog.geometry(f"{base_width}x{real_height}+{x}+{y}")

        # == STEP 6: Immediate show with enhanced macOS visibility ==
        dialog.attributes('-alpha', 1.0)  # Show immediately
        dialog.deiconify()  # Ensure it's not minimized
        dialog.focus_force()  # Force focus on macOS
        dialog.lift()
        dialog.attributes('-topmost', True)  # Bring to front
        
        # Additional macOS-specific visibility fixes
        try:
            dialog.update()
            dialog.focus_set()
            dialog.grab_set()  # Modal behavior
        except Exception as focus_error:
            print(f"[_create_custom_dialog] Focus setting warning: {focus_error}")
        
        print(f"[_create_custom_dialog] Dialog positioned at {x}x{y}, size {base_width}x{real_height}")

        # == STEP 7: Wait for user to click a button or close ==
        try:
            print("[_create_custom_dialog] About to wait for dialog result")
            
            # Use a polling approach that works reliably across platforms;
            # on macOS it avoids wait_window() issues in certain contexts
            if sys.platform == "darwin":
                print("[_create_custom_dialog] Using polling approach for macOS compatibility")
            else:
                print("[_create_custom_dialog] Using polling approach")
            
            # Start a polling loop to check if dialog still exists
            start_time = time.time()
            timeout = 60.0  # 60 seconds timeout - enough time for user interaction

            while True:
                try:
                    # Check if dialog still exists
                    dialog.winfo_exists()
                    
                    # Process any pending events
                    try:
                        if parent and parent.winfo_exists():
                            parent.update()
                        dialog.update()
                    except tk.TclError:
                        # Dialog was destroyed
                        break
                    
                    # Check if we have a result (user clicked a button)
                    if result[0] is not None:
                        print(f"[_create_custom_dialog] Dialog closed via button, returning result: {result[0]}")
                        return result[0]
                    
                    # Check timeout
                    if time.time() - start_time > timeout:
                        print(f"[_create_custom_dialog] ⚠️ Dialog polling timed out after {timeout} seconds")
                        break
                    
                    # Small delay to prevent excessive CPU usage
                    time.sleep(0.05)
                    
                except tk.TclError:
                    # Dialog was destroyed (user closed it)
                    print("[_create_custom_dialog] Dialog was destroyed")
                    break
                except Exception as poll_error:
                    print(f"[_create_custom_dialog] Polling error: {poll_error}")
                    break
            
            # If we get here, something went wrong or dialog was closed
            print(f"[_create_custom_dialog] Polling ended, final result: {result[0]}")
            return result[0] if result[0] is not None else False
                
        except Exception as wait_error:
            print(f"[_create_custom_dialog] ❌ wait_window() failed: {wait_error}")
            # Clean up the dialog
            try:
                dialog.destroy()
            except:
                pass
            # Force fallback
            raise Exception("wait_window() failed on this platform")

    except Exception as e:
        print(f"[_create_custom_dialog] ❌ Exception during dialog creation: {e}")
        import traceback
        traceback.print_exc()
        raise e  # Re-raise to trigger fallback in show_message


def _create_enhanced_buttons(dialog, button_frame, message_type, config, result, on_window_close, auto_close_timer=None, countdown_timer=None):
    """
    Create "OK" or "Yes/No" or "Retry/Cancel" buttons with enhanced styles - OPTIMIZED
    """
    def cancel_auto_close_timers():
        """Cancel both auto-close timers when user interacts with buttons"""
        if auto_close_timer and auto_close_timer[0] is not None:
            try:
                dialog.after_cancel(auto_close_timer[0])
                auto_close_timer[0] = None
                print("[_create_enhanced_buttons] Auto-close timer cancelled - user clicked button")
            except Exception as timer_error:
                print(f"[_create_enhanced_buttons] Auto-close timer cancel error: {timer_error}")
        
        if countdown_timer and countdown_timer[0] is not None:
            try:
                dialog.after_cancel(countdown_timer[0])
                countdown_timer[0] = None
                print("[_create_enhanced_buttons] Countdown timer cancelled - user clicked button")
            except Exception as timer_error:
                print(f"[_create_enhanced_buttons] Countdown timer cancel error: {timer_error}")
    
    if message_type in ["error", "warning", "info"]:
        def on_ok():
            cancel_auto_close_timers()
            result[0] = True
            try:
                dialog.after_idle(on_window_close)
            except:
                on_window_close()

        ok_btn = _create_cross_platform_button(
            button_frame,
            text="OK",
            command=on_ok,
            style=config['primary_style'],
            width=14
        )
        ok_btn.pack(side="right")

        # Batch event binding
        for event in ["<Return>", "<Escape>", "<space>"]:
            dialog.bind(event, lambda e: on_ok())

        ok_btn.focus_set()

    elif message_type == "yesno":
        def on_yes():
            cancel_auto_close_timers()
            result[0] = True
            try:
                dialog.after_idle(on_window_close)
            except:
                on_window_close()

        def on_no():
            cancel_auto_close_timers()
            result[0] = False
            try:
                dialog.after_idle(on_window_close)
            except:
                on_window_close()

        no_btn = _create_cross_platform_button(
            button_frame,
            text="No",
            command=on_no,
            style=config['secondary_style'],
            width=14
        )
        no_btn.pack(side="right", padx=(12, 0))

        yes_btn = _create_cross_platform_button(
            button_frame,
            text="Yes",
            command=on_yes,
            style=config['primary_style'],
            width=14
        )
        yes_btn.pack(side="right")

        # Batch event binding
        dialog.bind("<Return>", lambda e: on_yes())
        dialog.bind("<Escape>", lambda e: on_no())
        for key in ["<y>", "<Y>"]:
            dialog.bind(key, lambda e: on_yes())
        for key in ["<n>", "<N>"]:
            dialog.bind(key, lambda e: on_no())

        yes_btn.focus_set()

    elif message_type == "retrycancel":
        def on_retry():
            cancel_auto_close_timers()
            result[0] = True
            try:
                dialog.after_idle(on_window_close)
            except:
                on_window_close()

        def on_cancel():
            cancel_auto_close_timers()
            result[0] = False
            try:
                dialog.after_idle(on_window_close)
            except:
                on_window_close()

        cancel_btn = _create_cross_platform_button(
            button_frame,
            text="Cancel",
            command=on_cancel,
            style=config['secondary_style'],
            width=14
        )
        cancel_btn.pack(side="right", padx=(12, 0))

        retry_btn = _create_cross_platform_button(
            button_frame,
            text="Retry",
            command=on_retry,
            style=config['primary_style'],
            width=14
        )
        retry_btn.pack(side="right")

        # Batch event binding
        dialog.bind("<Return>", lambda e: on_retry())
        dialog.bind("<Escape>", lambda e: on_cancel())
        for key in ["<r>", "<R>"]:
            dialog.bind(key, lambda e: on_retry())
        for key in ["<c>", "<C>"]:
            dialog.bind(key, lambda e: on_cancel())

        retry_btn.focus_set()


# -----------------------------------------------------------------------------
# Public API functions
# -----------------------------------------------------------------------------
def show_message(message_type, title, message, errorCode = "",
                 icon_path=None, auto_close=True, auto_close_timeout=30, **options):
    """
    Displays an enhanced dialog:
      • message_type: "error" / "warning" / "info" / "yesno" / "retrycancel"
      • title:        window title
      • message:      the text to show
      • errorCode:    the error code to show
      • icon_path:    a .ico file (used only if we fall back to standard tk.messagebox)
                      If None, will try cross-platform default paths
      • auto_close:   Whether to automatically close the dialog after timeout (default: True)
      • auto_close_timeout: Number of seconds before auto-closing (default: 30)
      • **options:    forwarded to standard messagebox on fallback.

    Returns:
      • For "info"/"warning"/"error": always True after OK.
      • For "yesno": True if "Yes", False if "No."
      • For "retrycancel": True if "Retry", False if "Cancel."
    """
    code_str = str(errorCode).strip() if errorCode is not None else ""
    message = f"{code_str}: {message}" if code_str else str(message)
    try:
        # If showing the specific fatal error, block click collection globally
        try:
            from Helper.Watermark.watermark_handler_for_trial_version import set_click_collection_blocked
            if message_type == "error" and isinstance(message, str):
                # message may include a code prefix, so match by substring, case-insensitive
                if "something went wrong please contact the administrator" in message.lower():
                    set_click_collection_blocked(True)
        except Exception:
            pass

        print(f"[showMessage] Attempting to create custom dialog: {message_type}")
        
        # Try custom dialog first (works with both ttkbootstrap and standard ttk)
        # The timeout mechanism will handle any hanging issues
        return _create_custom_dialog(message_type, title, message, errorCode, 
                                   auto_close=auto_close, 
                                   auto_close_timeout=auto_close_timeout, 
                                   **options)
    except Exception as e:
        # Fallback to standard tkinter.messagebox if anything fails
        print(f"[EnhancedDialog] ❌ Custom dialog failed: {e}. Falling back to standard messagebox.")
        
        # Use cross-platform icon path if none provided
        if icon_path is None:
            import os
            icon_paths = [
                os.path.join("assets", "Images", "welcome_image.ico"),
                os.path.join("Assets", "Images", "welcome_image.ico"),
                "welcome_image.ico",
                "icon.ico"
            ]
            for path in icon_paths:
                if os.path.exists(path):
                    icon_path = path
                    break

        # Only try to set icon if we found a valid path and we're on Windows
        if icon_path and sys.platform == "win32":
            try:
                _set_msgbox_icon_async(title, icon_path)
            except Exception as icon_error:
                print(f"[showMessage] Warning: Could not set icon: {icon_error}")

        # Return the appropriate standard messagebox
        try:
            print(f"[showMessage] Using standard messagebox for type: {message_type}")
            
            # Check if we're in the main thread (required for macOS Tkinter)
            import threading
            if threading.current_thread() is not threading.main_thread():
                print("[showMessage] Not in main thread, using console fallback")
                # Console-only fallback
                print(f"DIALOG [{message_type.upper()}] {title}")
                print(f"Message: {message}")
                if message_type in ["yesno"]:
                    response = input("Continue? (y/n): ").lower().startswith('y')
                    return response
                elif message_type in ["retrycancel"]:
                    response = input("Retry? (r/c): ").lower().startswith('r')
                    return response
                else:
                    return True
            
            # Ensure we have a root window for messagebox - more robust approach
            temp_root = None
            try:
                # Try to get existing root first
                root = tk._default_root
                if root is None or not root.winfo_exists():
                    raise Exception("No valid root")
            except:
                # Create temporary root if needed
                print("[showMessage] Creating temporary root for messagebox")
                temp_root = tk.Tk()
                temp_root.withdraw()  # Hide the root window
                temp_root.attributes('-alpha', 0.0)  # Make it invisible
                temp_root.update()  # Process pending events
            
            try:
                # Use the standard messagebox with better error handling
                if message_type == "error":
                    result = messagebox.showerror(title, message, **options)
                elif message_type == "warning":
                    result = messagebox.showwarning(title, message, **options)
                elif message_type == "info":
                    result = messagebox.showinfo(title, message, **options)
                elif message_type == "yesno":
                    result = messagebox.askyesno(title, message, **options)
                elif message_type == "retrycancel":
                    result = messagebox.askretrycancel(title, message, **options)
                else:
                    print(f"[showMessage] Unknown message_type: {message_type}, using info")
                    result = messagebox.showinfo(title, message, **options)
                
                print(f"[showMessage] Standard messagebox returned: {result}")
                return result if result is not None else True
                
            finally:
                # Clean up temporary root if we created one
                if temp_root:
                    try:
                        temp_root.destroy()
                    except:
                        pass
                        
        except Exception as fallback_error:
            print(f"[showMessage] ❌ Standard messagebox failed: {fallback_error}")
            # Ultimate fallback - console mode
            print(f"DIALOG [{message_type.upper()}] {title}")
            print(f"Message: {message}")
            if message_type in ["yesno"]:
                response = input("Continue? (y/n): ").lower().startswith('y')
                return response
            elif message_type in ["retrycancel"]:
                response = input("Retry? (r/c): ").lower().startswith('r')
                return response
            else:
                return True


def askretrycancel(title=None, message=None,
                   icon_path=None, auto_close=True, auto_close_timeout=30, **options):
    """
    Convenience alias for a Retry/Cancel dialog:
      returns True if "Retry" was clicked, False if "Cancel" or closed.
    """
    return show_message("retrycancel", title, message, icon_path=icon_path, 
                       auto_close=auto_close, auto_close_timeout=auto_close_timeout, **options)


# -----------------------------------------------------------------------------
# Example/Test harness
# -----------------------------------------------------------------------------
def test_enhanced_messageboxes():
    """
    Launch a small ttkbootstrap window with buttons to test each dialog type.
    """
    root = ttk.Window(themename="cosmo")
    root.title("Enhanced MessageBox Demo")
    root.geometry("400x300")

    def test_info():
        show_message(
            "info",
            "Information",
            "This is an enhanced information dialog with improved typography "
            "and modern design elements. It will auto-close in 30 seconds.",
            auto_close=True,
            auto_close_timeout=10  # Faster for demo
        )

    def test_warning():
        show_message(
            "warning",
            "Warning",
            "This is a warning message with better visual hierarchy "
            "and enhanced user experience. Auto-close disabled for this demo.",
            auto_close=False  # Disabled for demo
        )

    def test_error():
        show_message(
            "error",
            "Error",
            "An error occurred! This dialog features modern styling "
            "with smooth animations and better accessibility. Auto-close in 5 seconds.",
            auto_close=True,
            auto_close_timeout=5  # Very fast for demo
        )

    def test_yesno():
        result = show_message(
            "yesno",
            "Confirmation",
            "Do you want to proceed with this action?\n"
            "Enhanced keyboard navigation is available (Y/N). Will auto-close to 'No' in 15 seconds.",
            auto_close=True,
            auto_close_timeout=15
        )
        print(f"User selected: {'Yes' if result else 'No'}")

    def test_retry():
        result = show_message(
            "retrycancel",
            "Operation Failed",
            "The operation could not be completed. Would you like to retry?\n"
            "Enhanced with better button styling and interactions. Auto-close to 'Cancel' in 20 seconds.",
            auto_close=True,
            auto_close_timeout=20
        )
        print(f"User selected: {'Retry' if result else 'Cancel'}")

    ttk.Label(
        root,
        text="Enhanced MessageBox Demo",
        font=_get_system_font(16, "bold")
    ).pack(pady=20)

    button_frame = ttk.Frame(root)
    button_frame.pack(expand=True)

    ttk.Button(
        button_frame,
        text="Test Info Dialog",
        command=test_info,
        bootstyle="info",
        width=20
    ).pack(pady=5)

    ttk.Button(
        button_frame,
        text="Test Warning Dialog",
        command=test_warning,
        bootstyle="warning",
        width=20
    ).pack(pady=5)

    ttk.Button(
        button_frame,
        text="Test Error Dialog",
        command=test_error,
        bootstyle="danger",
        width=20
    ).pack(pady=5)

    ttk.Button(
        button_frame,
        text="Test Yes/No Dialog",
        command=test_yesno,
        bootstyle="primary",
        width=20
    ).pack(pady=5)

    ttk.Button(
        button_frame,
        text="Test Retry/Cancel Dialog",
        command=test_retry,
        bootstyle="secondary",
        width=20
    ).pack(pady=5)

    root.mainloop()


if __name__ == "__main__":
    test_enhanced_messageboxes()