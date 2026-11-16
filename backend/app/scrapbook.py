"""El álbum de recuerdos: fotos elegidas de la galería con un nombre para mostrar.

Es capa de aplicación (no procesa imágenes): guarda una lista ordenada en
`storage/scrapbook.json`. Cada entrada apunta a una imagen que ya existe en
storage/ (original, digitalizada, restaurada o retro) y conserva el nombre
que eligió el usuario para la foto.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path


class Scrapbook:
    def __init__(self, storage_dir: Path) -> None:
        self.storage_dir = Path(storage_dir)
        self.index_path = self.storage_dir / "scrapbook.json"

    # ------------------------------------------------------------------ índice

    def _load(self) -> dict:
        if not self.index_path.exists():
            return {"photos": []}
        data = json.loads(self.index_path.read_text(encoding="utf-8"))
        data.setdefault("photos", [])
        return data

    def _save(self, data: dict) -> None:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _exists(self, entry: dict) -> bool:
        return (self.storage_dir / entry["folder"] / entry["filename"]).is_file()

    # ------------------------------------------------------------------- fotos

    def all(self) -> dict:
        """El álbum completo; descarta fotos cuyo archivo ya no está en storage/."""
        data = self._load()
        photos = [entry for entry in data["photos"] if self._exists(entry)]
        if len(photos) != len(data["photos"]):
            data["photos"] = photos
            self._save(data)
        return data

    def add(
        self,
        name: str,
        source_kind: str,
        source_id: str,
        folder: str,
        filename: str,
        width: int,
        height: int,
    ) -> dict:
        data = self._load()
        if any(
            entry.get("source_kind") == source_kind and entry.get("source_id") == source_id
            for entry in data["photos"]
        ):
            raise ValueError("duplicate")

        entry = {
            "id": uuid.uuid4().hex[:12],
            "name": name,
            "source_kind": source_kind,
            "source_id": source_id,
            "folder": folder,
            "filename": filename,
            "width": int(width),
            "height": int(height),
            "added": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        data["photos"].append(entry)
        self._save(data)
        return entry

    def remove(self, item_id: str) -> bool:
        data = self._load()
        kept = [entry for entry in data["photos"] if entry["id"] != item_id]
        if len(kept) == len(data["photos"]):
            return False
        data["photos"] = kept
        self._save(data)
        return True

    def clear(self) -> int:
        """Vacía las fotos del álbum y deja la portada como estaba."""
        data = self._load()
        count = len(data["photos"])
        if count:
            data["photos"] = []
            self._save(data)
        return count
