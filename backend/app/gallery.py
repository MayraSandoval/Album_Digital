"""La galería: guarda los resultados de Digitalizar y Restaurar por separado.

Es capa de aplicación (no procesa imágenes): administra archivos y metadatos.

    storage/scanned/    → todo lo que pasó por "1. Digitalizar"
    storage/restored/   → todo lo que pasó por "3. Restauración"
    storage/retro/      → todo lo que pasó por "4. Estilo retro"
    storage/gallery.json → índice con tipo, tamaño y fecha de cada foto
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

SCANNED = "scanned"
RESTORED = "restored"
RETRO = "retro"


class Gallery:
    def __init__(self, storage_dir: Path) -> None:
        self.storage_dir = Path(storage_dir)
        self.folders = {
            SCANNED: self.storage_dir / SCANNED,
            RESTORED: self.storage_dir / RESTORED,
            RETRO: self.storage_dir / RETRO,
        }
        self.index_path = self.storage_dir / "gallery.json"

    # ------------------------------------------------------------------ índice

    def _load(self) -> list[dict]:
        if not self.index_path.exists():
            return []
        return json.loads(self.index_path.read_text(encoding="utf-8"))

    def _save(self, entries: list[dict]) -> None:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")

    def _write(self, folder: str, filename: str, png: bytes) -> None:
        self.folders[folder].mkdir(parents=True, exist_ok=True)
        (self.folders[folder] / filename).write_bytes(png)

    # ------------------------------------------------------------------ fotos

    def add_scanned(self, png: bytes, width: int, height: int) -> dict:
        item_id = uuid.uuid4().hex[:12]
        entry = {
            "id": item_id,
            "kind": SCANNED,
            "folder": SCANNED,
            "filename": f"{item_id}.png",
            "width": int(width),
            "height": int(height),
            "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        self._write(SCANNED, entry["filename"], png)
        entries = self._load()
        entries.append(entry)
        self._save(entries)
        return entry

    def add_restored(self, source_id: str, png: bytes, width: int, height: int) -> dict:
        """Una restauración por foto original: si se repite, se reemplaza."""
        entry = {
            "id": source_id,
            "kind": RESTORED,
            "folder": RESTORED,
            "filename": f"{source_id}.png",
            "width": int(width),
            "height": int(height),
            "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source_id": source_id,
        }
        self._write(RESTORED, entry["filename"], png)
        entries = [e for e in self._load() if not (e.get("kind") == RESTORED and e.get("source_id") == source_id)]
        entries.append(entry)
        self._save(entries)
        return entry

    def add_retro(
        self,
        source_id: str,
        png: bytes,
        width: int,
        height: int,
        palette: str,
        dithering: bool,
    ) -> dict:
        """Cada aplicación crea una variante nueva; se acumulan por foto original."""
        item_id = uuid.uuid4().hex[:12]
        entry = {
            "id": item_id,
            "kind": RETRO,
            "folder": RETRO,
            "filename": f"{item_id}.png",
            "width": int(width),
            "height": int(height),
            "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source_id": source_id,
            "palette": palette,
            "dithering": bool(dithering),
        }
        self._write(RETRO, entry["filename"], png)
        entries = self._load()
        entries.append(entry)
        self._save(entries)
        return entry

    def remove_scanned(self, item_id: str) -> bool:
        entries = self._load()
        kept = []
        removed = False
        for entry in entries:
            if entry.get("kind") == SCANNED and entry.get("id") == item_id:
                (self.folders[SCANNED] / entry["filename"]).unlink(missing_ok=True)
                removed = True
            else:
                kept.append(entry)
        if removed:
            self._save(kept)
        return removed

    def remove_restored(self, source_id: str) -> bool:
        entries = self._load()
        kept = []
        removed = False
        for entry in entries:
            if entry.get("kind") == RESTORED and entry.get("source_id") == source_id:
                (self.folders[RESTORED] / entry["filename"]).unlink(missing_ok=True)
                removed = True
            else:
                kept.append(entry)
        if removed:
            self._save(kept)
        return removed

    def remove_retro(self, source_id: str) -> bool:
        """Borra todas las variantes retro de una foto original."""
        entries = self._load()
        kept = []
        removed = False
        for entry in entries:
            if entry.get("kind") == RETRO and entry.get("source_id") == source_id:
                (self.folders[RETRO] / entry["filename"]).unlink(missing_ok=True)
                removed = True
            else:
                kept.append(entry)
        if removed:
            self._save(kept)
        return removed

    def remove_retro_item(self, item_id: str) -> bool:
        """Borra una sola variante retro de la galería."""
        entries = self._load()
        kept = []
        removed = False
        for entry in entries:
            if entry.get("kind") == RETRO and entry.get("id") == item_id:
                (self.folders[RETRO] / entry["filename"]).unlink(missing_ok=True)
                removed = True
            else:
                kept.append(entry)
        if removed:
            self._save(kept)
        return removed

    def all(self) -> list[dict]:
        return self._load()
