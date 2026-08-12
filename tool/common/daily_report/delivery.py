from __future__ import annotations

import json
from pathlib import Path


class DeliveryModeStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load(self) -> str:
        if not self.path.is_file():
            return "public"
        value = str(json.loads(self.path.read_text("utf-8")).get("mode", "public"))
        return value if value in {"public", "personal"} else "public"

    def save(self, mode: str) -> str:
        mode = str(mode)
        if mode not in {"public", "personal"}:
            raise ValueError("Delivery mode must be public or personal")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"mode": mode}, indent=2), "utf-8")
        temporary.replace(self.path)
        return mode
