from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from app_paths import AppPathManager


@dataclass(frozen=True)
class GeneratedLayoutStorage:
    """
    Persist generated layout payloads into a dedicated app-data folder.
    """

    def ensure_dir(self) -> str:
        AppPathManager.ensure_directories()
        gen_dir = AppPathManager.get_generated_layouts_dir()
        Path(gen_dir).mkdir(parents=True, exist_ok=True)
        return gen_dir

    def save_json(self, payload: Dict[str, Any]) -> str:
        gen_dir = self.ensure_dir()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        token = uuid.uuid4().hex[:8]
        filename = f"generated_layout_{ts}_{token}.json"
        path = os.path.join(gen_dir, filename)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

        return path

