# local_autosave.py
# Crash-safe local autosave for your Mini-AutoCAD.
# Hooks actions.log so EVERY user action writes an atomic JSON snapshot.
# Also supports a tiny debounce mode and rotating backups.
#
# Usage in app.pyw (example):
#   from app_paths import AppPathManager
#   from local_autosave import LocalAutosave, try_load_json
#   serializer = LayoutSerializer(model, view, tools, actions)
#   AppPathManager.ensure_directories()
#   autosaver = LocalAutosave(
#       root,
#       serializer,
#       actions,
#       path=AppPathManager.get_autosave_file(),
#       save_every_action=True,     # write on every action
#       throttle_ms=0,              # no debounce
#       backups_dir=AppPathManager.get_backups_dir(),
#       keep_last=10,               # keep last 10 backups
#       heartbeat_sec=0             # optional periodic save; 0 = off
#   )
#   autosaver.wrap_action_logger()
#   # Optional: on startup, auto-restore last autosave:
#   data = try_load_json(autosaver.path)
#   if data: serializer.import_from_dict(data)
#
import json
import os
import time
from typing import Optional

from layout_serializer import atomic_write_document

class _Debouncer:
    def __init__(self, root, delay_ms, func):
        self.root = root
        self.delay_ms = max(0, int(delay_ms or 0))
        self.func = func
        self._timer = None
    def trigger(self):
        if self.delay_ms <= 0:
            self.func()
            return
        if self._timer:
            self.root.after_cancel(self._timer)
        self._timer = self.root.after(self.delay_ms, self._run)
    def _run(self):
        self._timer = None
        self.func()
    def cancel(self):
        if self._timer:
            try:
                self.root.after_cancel(self._timer)
            except Exception:
                pass
            self._timer = None

def _atomic_json_dump(obj, path: str):
    """Compatibility wrapper around the serializer's single atomic writer."""
    atomic_write_document(obj, path)

def _timestamp():
    return time.strftime("%Y%m%d-%H%M%S", time.localtime())

def try_load_json(path: str):
    """Return loaded dict if file exists, else None."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except Exception as e:
        print("[LocalAutosave] Failed to load:", e)
        return None

class LocalAutosave:
    def __init__(self, root, serializer, actions, path: str,
                 save_every_action: bool = True,
                 throttle_ms: int = 0,
                 backups_dir: Optional[str] = None,
                 keep_last: int = 10,
                 heartbeat_sec: int = 0):
        self.root = root
        self.serializer = serializer
        self.actions = actions
        self.path = path
        self.save_every_action = save_every_action
        self.keep_last = max(0, int(keep_last))
        self.backups_dir = backups_dir
        self.heartbeat_sec = max(0, int(heartbeat_sec or 0))
        self._orig_log = None
        self._deb = _Debouncer(root, throttle_ms, self.save_now)
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if self.backups_dir:
            os.makedirs(self.backups_dir, exist_ok=True)
        self._hb_after_id = None

    # Kept as compatibility lifecycle methods; action notifications are now
    # registered through ActionManager.post_mutation_callback, never monkey-patched.
    def wrap_action_logger(self):
        if self.heartbeat_sec > 0 and self._hb_after_id is None:
            self._schedule_heartbeat()

    def schedule(self):
        """Write immediately or through the configured debounce."""
        if self.save_every_action and self._deb.delay_ms <= 0:
            self.save_now()
        else:
            self._deb.trigger()

    def unwrap_action_logger(self):
        self._deb.cancel()
        if getattr(self, "_hb_after_id", None):
            try:
                self.root.after_cancel(self._hb_after_id)
            except Exception:
                pass
            self._hb_after_id = None

    # ---- Save operations ----------------------------------------------
    def save_now(self):
        try:
            data = self.serializer.serialize_layout()
        except Exception as e:
            print("[LocalAutosave] serialize failed:", e)
            return
        # Atomic write
        try:
            _atomic_json_dump(data, self.path)
        except Exception as e:
            print("[LocalAutosave] write failed:", e)
            return
        # Optional rolling backup
        if self.backups_dir and self.keep_last > 0:
            self._write_backup(data)

    def _write_backup(self, data):
        try:
            name = f"autosave-{_timestamp()}.json"
            bpath = os.path.join(self.backups_dir, name)
            _atomic_json_dump(data, bpath)
            # trim old backups
            files = sorted(
                [f for f in os.listdir(self.backups_dir) if f.endswith('.json')]
            )
            excess = len(files) - self.keep_last
            for i in range(excess):
                try:
                    os.remove(os.path.join(self.backups_dir, files[i]))
                except Exception:
                    pass
        except Exception as e:
            print("[LocalAutosave] backup failed:", e)

    # ---- Heartbeat (optional) -----------------------------------------
    def _schedule_heartbeat(self):
        def _tick():
            try:
                # Check if window still exists before saving
                if not hasattr(self.root, 'winfo_exists') or not self.root.winfo_exists():
                    self._hb_after_id = None
                    return
                self.save_now()
            except Exception as e:
                # If window is destroyed, stop scheduling
                try:
                    if not self.root.winfo_exists():
                        self._hb_after_id = None
                        return
                except Exception:
                    self._hb_after_id = None
                    return
                print(f"[LocalAutosave] Heartbeat error: {e}")
            finally:
                # Only reschedule if window still exists
                try:
                    if hasattr(self.root, 'winfo_exists') and self.root.winfo_exists():
                        self._schedule_heartbeat()
                    else:
                        self._hb_after_id = None
                except Exception:
                    self._hb_after_id = None
        self._hb_after_id = self.root.after(self.heartbeat_sec * 1000, _tick)

# # local_autosave.py
# # Debounced local autosave that hooks actions.log (similar to cloud autosave).
# import json
# import os

# class _Debouncer:
#     def __init__(self, root, delay_ms, func):
#         self.root = root
#         self.delay_ms = delay_ms
#         self.func = func
#         self._timer = None
#     def trigger(self):
#         if self._timer:
#             self.root.after_cancel(self._timer)
#         self._timer = self.root.after(self.delay_ms, self.func)

# class LocalAutosave:
#     def __init__(self, root, serializer, actions, path, throttle_ms=400):
#         self.root = root
#         self.serializer = serializer
#         self.actions = actions
#         self.path = path
#         self._orig_log = None
#         self._deb = _Debouncer(root, throttle_ms, self.save_now)
#         os.makedirs(os.path.dirname(path), exist_ok=True)

#     def wrap_action_logger(self):
#         if self._orig_log is not None:
#             return
#         original_log = getattr(self.actions, "log", None)
#         if not callable(original_log):
#             raise RuntimeError("Expected actions.log(call) to exist and be callable.")
#         self._orig_log = original_log

#         def wrapped(entry):
#             self._orig_log(entry)
#             self._deb.trigger()

#         setattr(self.actions, "log", wrapped)

#     def unwrap_action_logger(self):
#         if self._orig_log is not None:
#             setattr(self.actions, "log", self._orig_log)
#             self._orig_log = None

#     def save_now(self):
#         data = self.serializer.export_to_dict()
#         with open(self.path, "w", encoding="utf-8") as f:
#             json.dump(data, f, ensure_ascii=False, indent=2)
