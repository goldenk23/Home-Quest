import os
import sys
from dataclasses import dataclass


def get_asset_root() -> str:
    """Return the centralized, read-only application asset directory."""
    app_dir = os.path.dirname(os.path.abspath(__file__))
    bases = [
        getattr(sys, "_MEIPASS", ""),
        os.environ.get("VASTUAPP_HOME", ""),
        os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else "",
        app_dir,
    ]
    for base in bases:
        candidate = os.path.join(base, "assets") if base else ""
        if candidate and os.path.isdir(candidate):
            return candidate
    return os.path.join(app_dir, "assets")


@dataclass(frozen=True)
class AppPathManager:
    """
    Centralized, cross-platform path manager for MiniAutoCAD / Vastu app data.

    - On Windows:  %LOCALAPPDATA%\\VastuApp\\...
    - On macOS:    ~/Library/Application Support/VastuApp/...
    - On Linux:    $XDG_DATA_HOME/VastuApp or ~/.local/share/VastuApp/...
    """

    app_name: str = "VastuApp"

    @classmethod
    def _base_appdata_dir(cls) -> str:
        """Return the OS-specific base directory for storing app data."""
        home = os.path.expanduser("~")

        if os.name == "nt":
            # Windows → prefer LOCALAPPDATA, fall back to AppData/Local
            base = os.environ.get("LOCALAPPDATA") or os.path.join(
                home, "AppData", "Local"
            )
        elif sys.platform == "darwin":
            # macOS → standard Application Support path
            base = os.path.join(home, "Library", "Application Support")
        else:
            # Linux / Unix → XDG spec, then ~/.local/share
            base = os.environ.get("XDG_DATA_HOME") or os.path.join(
                home, ".local", "share"
            )

        return os.path.join(base, cls.app_name)

    # ---- Public helpers -------------------------------------------------
    @classmethod
    def get_app_root(cls) -> str:
        """Root directory for this app's data (e.g., .../VastuApp)."""
        return cls._base_appdata_dir()

    @classmethod
    def get_saved_layouts_dir(cls) -> str:
        """Directory where all saved layout JSON/YAML files should live."""
        return os.path.join(cls.get_app_root(), "saved_layouts")

    @classmethod
    def get_autosave_file(cls) -> str:
        """Full path to the primary autosave JSON file."""
        return os.path.join(cls.get_saved_layouts_dir(), "autosave.json")

    @classmethod
    def get_backups_dir(cls) -> str:
        """Directory containing rolling autosave backup files."""
        return os.path.join(cls.get_saved_layouts_dir(), "backups")

    @classmethod
    def get_generated_layouts_dir(cls) -> str:
        """
        Directory for auto-saved files created by the "Generate Layout" feature.
        Kept separate from user-driven save/load files.
        """
        return os.path.join(cls.get_app_root(), "generated_layouts")

    @classmethod
    def ensure_directories(cls) -> None:
        """
        Create the key directories if they do not exist.
        Safe to call multiple times.
        """
        for path in (
            cls.get_saved_layouts_dir(),
            cls.get_backups_dir(),
            cls.get_generated_layouts_dir(),
        ):
            os.makedirs(path, exist_ok=True)

