"""Configuraciones de restauración guardadas por el usuario.

Es capa de aplicación, como Album y Gallery: solo administra un índice JSON
(`storage/presets.json`). Cada configuración guarda los pasos manuales con sus
parámetros, en el orden en que se aplicaron.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path


class PresetStore:
    def __init__(self, storage_dir: Path) -> None:
        self.storage_dir = Path(storage_dir)
        self.index_path = self.storage_dir / "presets.json"

    def _load(self) -> list[dict]:
        if not self.index_path.exists():
            return []
        return json.loads(self.index_path.read_text(encoding="utf-8"))

    def _save(self, entries: list[dict]) -> None:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")

    def all(self) -> list[dict]:
        return self._load()

    def get(self, preset_id: str) -> dict | None:
        return next((entry for entry in self._load() if entry["id"] == preset_id), None)

    def save(self, name: str, steps: list[dict]) -> dict:
        """Guarda o actualiza por nombre, sin distinguir mayúsculas."""
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        entries = self._load()
        key = name.strip().casefold()
        entry = next((item for item in entries if item["name"].strip().casefold() == key), None)
        if entry is None:
            entry = {
                "id": uuid.uuid4().hex[:12],
                "name": name.strip(),
                "steps": steps,
                "created": now,
                "updated": now,
            }
            entries.append(entry)
        else:
            entry["name"] = name.strip()
            entry["steps"] = steps
            entry["updated"] = now
        self._save(entries)
        return entry

    def delete(self, preset_id: str) -> bool:
        entries = self._load()
        kept = [entry for entry in entries if entry["id"] != preset_id]
        if len(kept) == len(entries):
            return False
        self._save(kept)
        return True
