"""Implementaciones de los almacenes sobre Postgres y Supabase Storage."""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock

from album import NotImplementedYet, decode, encode_png, inspect, limit_side
from album.descriptors import perceptual_hash

from app.album import Album
from app.gallery import RESTORED, RETRO, SCANNED, Gallery
from app.presets import PresetStore
from app.scrapbook import Scrapbook
from app.supabase_client import SupabaseClient, SupabaseConflict, SupabaseError


_clock_lock = Lock()
_last_timestamp: datetime | None = None


def _now() -> str:
    # Desempata inserciones del mismo proceso para conservar su orden.
    global _last_timestamp
    with _clock_lock:
        now = datetime.now(timezone.utc)
        if _last_timestamp is not None and now <= _last_timestamp:
            now = _last_timestamp + timedelta(microseconds=1)
        _last_timestamp = now
    return now.isoformat(timespec="microseconds")


def _no_bulk_save(self, data) -> None:
    """No sustituir colecciones completas ni escribir el índice local."""
    raise NotImplementedError("Los almacenes remotos se actualizan por identificador")


def _delete_file_if_present(client: SupabaseClient, folder: str, filename: str) -> None:
    if client.get_file(folder, filename) is not None:
        client.delete_file(folder, filename)


# Una inserción fallida puede haberse confirmado; no se borran archivos como compensación.
class SupabaseAlbum(Album):
    def __init__(self, storage_dir: Path, client: SupabaseClient) -> None:
        super().__init__(storage_dir)
        self.client = client

    _save = _no_bulk_save

    @staticmethod
    def _with_restoration(entry: dict, restored: dict | None) -> dict:
        result = {**entry, "restored": restored is not None}
        if restored is None:
            result.pop("restored_url", None)
        else:
            result["restored_url"] = f"{restored['folder']}/{restored['filename']}"
        return result

    def _load(self) -> list[dict]:
        photos = self.client.rows("photos")
        restored = {
            item["source_id"]: item for item in self.client.rows("gallery") if item.get("kind") == RESTORED
        }
        return sorted(
            (self._with_restoration(entry, restored.get(entry["id"])) for entry in photos),
            key=lambda entry: entry.get("created", ""),
        )

    def all(self) -> list[dict]:
        return self._load()

    def get(self, photo_id: str) -> dict | None:
        entry = self.client.get("photos", photo_id)
        if entry is None:
            return None
        restored = self.client.get("gallery", photo_id)
        if restored is not None and (restored.get("kind") != RESTORED or restored.get("source_id") != photo_id):
            restored = None
        return self._with_restoration(entry, restored)

    def add(self, data: bytes) -> dict:
        info = inspect(data)
        image = limit_side(decode(data))
        photo_id = uuid.uuid4().hex[:12]
        entry = {
            "id": photo_id,
            "filename": f"{photo_id}.png",
            "width": int(image.shape[1]),
            "height": int(image.shape[0]),
            "mode": info.mode,
            "size_bytes": len(data),
            "restored": False,
            "created": _now(),
            "phash": None,
        }
        try:
            entry["phash"] = perceptual_hash(image)
        except NotImplementedYet:
            pass
        self.client.put_file("photos", entry["filename"], encode_png(image))
        self.client.insert("photos", entry)
        return entry

    def delete(self, photo_id: str) -> bool:
        entry = self.get(photo_id)
        if entry is None:
            return False
        _delete_file_if_present(self.client, "photos", entry["filename"])
        return self.client.delete("photos", photo_id)

    def read_image(self, entry: dict):
        data = self.client.get_file("photos", entry["filename"])
        if data is None:
            raise FileNotFoundError(f"photos/{entry['filename']}")
        return decode(data)

    # El registro de la galería es la única fuente de la restauración actual.
    def mark_restored(self, entry: dict, restored_path: str) -> None:
        pass

    def clear_restored(self, photo_id: str) -> None:
        pass


class SupabaseGallery(Gallery):
    def __init__(self, storage_dir: Path, client: SupabaseClient) -> None:
        super().__init__(storage_dir)
        self.client = client

    _save = _no_bulk_save

    def _load(self) -> list[dict]:
        return sorted(self.client.rows("gallery"), key=lambda entry: entry.get("created", ""))

    def _write(self, folder: str, filename: str, png: bytes) -> None:
        self.client.put_file(folder, filename, png)

    def all(self) -> list[dict]:
        return self._load()

    def all_with_legacy(self, album_entries: list[dict]) -> list[dict]:
        # Los archivos antiguos del disco local no se migran ni se consultan.
        return self.all()

    def add_scanned(self, png: bytes, width: int, height: int) -> dict:
        item_id = uuid.uuid4().hex[:12]
        entry = {
            "id": item_id,
            "kind": SCANNED,
            "folder": SCANNED,
            "filename": f"{item_id}.png",
            "width": int(width),
            "height": int(height),
            "created": _now(),
        }
        self._write(SCANNED, entry["filename"], png)
        self.client.insert("gallery", entry)
        return entry

    def add_restored(self, source_id: str, png: bytes, width: int, height: int) -> dict:
        current = self.client.get("gallery", source_id)
        if current is not None and (
            current.get("kind") != RESTORED or current.get("source_id") != source_id
        ):
            raise SupabaseConflict("El identificador ya pertenece a otra imagen de la galería")
        entry = {
            "id": source_id,
            "kind": RESTORED,
            "folder": RESTORED,
            "filename": f"{source_id}_{uuid.uuid4().hex[:12]}.png",
            "width": int(width),
            "height": int(height),
            "created": _now(),
            "source_id": source_id,
        }
        previous_path = (current["folder"], current["filename"]) if current is not None else None
        if previous_path == (entry["folder"], entry["filename"]):
            raise SupabaseConflict("La nueva versión coincide con el archivo anterior")
        self._write(RESTORED, entry["filename"], png)
        self.client.upsert("gallery", entry)
        if previous_path is not None:
            try:
                self.client.delete_file(*previous_path)
            except SupabaseError:
                logging.getLogger(__name__).warning(
                    "No se pudo eliminar el archivo de la restauración anterior."
                )
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
        item_id = uuid.uuid4().hex[:12]
        entry = {
            "id": item_id,
            "kind": RETRO,
            "folder": RETRO,
            "filename": f"{item_id}.png",
            "width": int(width),
            "height": int(height),
            "created": _now(),
            "source_id": source_id,
            "palette": palette,
            "dithering": bool(dithering),
        }
        self._write(RETRO, entry["filename"], png)
        self.client.insert("gallery", entry)
        return entry

    def _remove_entry(self, entry: dict) -> bool:
        _delete_file_if_present(self.client, entry["folder"], entry["filename"])
        return self.client.delete("gallery", entry["id"])

    def remove_scanned(self, item_id: str) -> bool:
        entry = self.client.get("gallery", item_id)
        return bool(entry and entry.get("kind") == SCANNED and self._remove_entry(entry))

    def remove_restored(self, source_id: str) -> bool:
        entry = self.client.get("gallery", source_id)
        return bool(
            entry
            and entry.get("kind") == RESTORED
            and entry.get("source_id") == source_id
            and self._remove_entry(entry)
        )

    def remove_retro(self, source_id: str) -> bool:
        removed = False
        for entry in self._load():
            if entry.get("kind") == RETRO and entry.get("source_id") == source_id:
                if self._remove_entry(entry):
                    removed = True
        return removed

    def remove_retro_item(self, item_id: str) -> bool:
        entry = self.client.get("gallery", item_id)
        return bool(entry and entry.get("kind") == RETRO and self._remove_entry(entry))


class SupabasePresetStore(PresetStore):
    def __init__(self, storage_dir: Path, client: SupabaseClient) -> None:
        super().__init__(storage_dir)
        self.client = client

    _save = _no_bulk_save

    def _load(self) -> list[dict]:
        return sorted(self.client.rows("presets"), key=lambda entry: entry.get("created", ""))

    def all(self) -> list[dict]:
        return self._load()

    def get(self, preset_id: str) -> dict | None:
        return self.client.get("presets", preset_id)

    def save(self, name: str, steps: list[dict]) -> dict:
        now = _now()
        name = name.strip()
        key = hashlib.sha256(name.casefold().encode("utf-8")).hexdigest()
        current = self.client.get_unique("presets", key)
        if current is None:
            entry = {
                "id": uuid.uuid4().hex[:12],
                "name": name,
                "steps": steps,
                "created": now,
                "updated": now,
            }
            try:
                self.client.insert("presets", entry, unique_key=key)
                return entry
            except SupabaseConflict:
                # Otro escritor pudo crear el mismo nombre tras get_unique.
                current = self.client.get_unique("presets", key)
                if current is None:
                    raise
        entry = {**current, "name": name, "steps": steps, "updated": now}
        self.client.upsert("presets", entry, unique_key=key)
        return entry

    def delete(self, preset_id: str) -> bool:
        return self.client.delete("presets", preset_id)


class SupabaseScrapbook(Scrapbook):
    def __init__(self, storage_dir: Path, client: SupabaseClient) -> None:
        super().__init__(storage_dir)
        self.client = client

    _save = _no_bulk_save

    def _load(self) -> dict:
        photos = sorted(self.client.rows("scrapbook"), key=lambda entry: entry.get("added", ""))
        return {"photos": photos}

    def _exists(self, entry: dict) -> bool:
        return self.client.get_file(entry["folder"], entry["filename"]) is not None

    def all(self) -> dict:
        photos = self._load()["photos"]
        available = {
            ("original", entry["id"]): ("photos", entry["filename"])
            for entry in self.client.rows("photos")
        }
        available.update({
            (entry["kind"], entry["id"]): (entry["folder"], entry["filename"])
            for entry in self.client.rows("gallery")
        })
        resolved = []
        for entry in photos:
            path = available.get((entry["source_kind"], entry["source_id"]))
            if path is not None:
                folder, filename = path
                resolved.append({**entry, "folder": folder, "filename": filename})
        return {"photos": resolved}

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
        entry = {
            "id": uuid.uuid4().hex[:12],
            "name": name,
            "source_kind": source_kind,
            "source_id": source_id,
            "folder": folder,
            "filename": filename,
            "width": int(width),
            "height": int(height),
            "added": _now(),
        }
        # JSON evita colisiones entre componentes que contienen separadores.
        key = json.dumps([source_kind, source_id], ensure_ascii=False, separators=(",", ":"))
        try:
            self.client.insert("scrapbook", entry, unique_key=key)
        except SupabaseConflict as exc:
            raise ValueError("duplicate") from exc
        return entry

    def remove(self, item_id: str) -> bool:
        return self.client.delete("scrapbook", item_id)

    def remove_source(self, source_kind: str, source_id: str) -> int:
        count = 0
        for entry in self.client.rows("scrapbook"):
            if entry.get("source_kind") == source_kind and entry.get("source_id") == source_id:
                if self.client.delete("scrapbook", entry["id"]):
                    count += 1
        return count

    def clear(self) -> int:
        count = 0
        for entry in self.client.rows("scrapbook"):
            if self.client.delete("scrapbook", entry["id"]):
                count += 1
        return count
