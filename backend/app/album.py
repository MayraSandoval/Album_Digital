"""El álbum: guarda las fotos en disco y las indexa en un JSON.

Esta clase es de la capa de aplicación (no del core): no procesa imágenes,
solo administra archivos y metadatos. Todo el procesamiento real pasa por
`album.*` (el core).

Dos fotos son "casi iguales" si sus hashes perceptuales difieren en a lo
sumo DUPLICATE_BITS de los 64 bits.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from album import NotImplementedYet, decode, encode_png, inspect, limit_side
from album import descriptors
from album.descriptors import hamming, perceptual_hash

DUPLICATE_BITS = 10


class Album:
    def __init__(self, storage_dir: Path) -> None:
        self.storage_dir = Path(storage_dir)
        self.photos_dir = self.storage_dir / "photos"
        self.index_path = self.storage_dir / "album.json"

    # ------------------------------------------------------------------ index

    def _load(self) -> list[dict]:
        if not self.index_path.exists():
            return []
        return json.loads(self.index_path.read_text(encoding="utf-8"))

    def _save(self, entries: list[dict]) -> None:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")

    # ------------------------------------------------------------------ fotos

    def add(self, data: bytes) -> dict:
        """Guarda la foto (re-encodeada como PNG) y la indexa.

        Calcula el hash perceptual si ya está implementado: sirve para avisar
        duplicados. Devuelve la entrada creada.
        """
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
            "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "phash": None,
        }
        try:
            entry["phash"] = perceptual_hash(image)
        except NotImplementedYet:
            pass  # descriptors todavía no está: sin control de duplicados por ahora
        self.photos_dir.mkdir(parents=True, exist_ok=True)
        (self.photos_dir / entry["filename"]).write_bytes(encode_png(image))
        entries = self._load()
        entries.append(entry)
        self._save(entries)
        return entry

    def all(self) -> list[dict]:
        return self._load()

    def get(self, photo_id: str) -> dict | None:
        return next((e for e in self._load() if e["id"] == photo_id), None)

    def delete(self, photo_id: str) -> bool:
        entries = self._load()
        kept = [e for e in entries if e["id"] != photo_id]
        if len(kept) == len(entries):
            return False
        self._save(kept)
        for name in (f"{photo_id}.png", f"{photo_id}_restored.png"):
            path = self.photos_dir / name
            if path.exists():
                path.unlink()
        return True

    def read_image(self, entry: dict):
        return decode((self.photos_dir / entry["filename"]).read_bytes())

    def mark_restored(self, entry: dict, image) -> None:
        (self.photos_dir / f"{entry['id']}_restored.png").write_bytes(encode_png(image))
        entries = self._load()
        for e in entries:
            if e["id"] == entry["id"]:
                e["restored"] = True
        self._save(entries)

    # ------------------------------------------------------------- duplicados

    def duplicates_of(self, entry: dict) -> list[dict]:
        phash = entry.get("phash")
        if phash is None:
            return []
        found = []
        for other in self._load():
            if other["id"] == entry["id"] or other.get("phash") is None:
                continue
            if hamming(phash, other["phash"]) <= DUPLICATE_BITS:
                found.append(other)
        return found

    # --------------------------------------------------------------- búsquedas

    def search_by_color(self, rgb: tuple[int, int, int], min_fraction: float) -> list[tuple[dict, float]]:
        """[(foto, fracción)] con fracción ≥ min_fraction, de mayor a menor."""
        results = []
        for entry in self._load():
            fraction = descriptors.color_fraction(self.read_image(entry), rgb)
            if fraction >= min_fraction:
                results.append((entry, float(fraction)))
        return sorted(results, key=lambda pair: pair[1], reverse=True)

    def search_similar(self, photo_id: str) -> list[tuple[dict, float]]:
        """Las demás fotos rankeadas por distancia de histograma (menor = más parecida)."""
        entries = self._load()
        query = next((e for e in entries if e["id"] == photo_id), None)
        if query is None:
            raise KeyError(photo_id)
        query_hist = descriptors.color_histogram(self.read_image(query))
        results = []
        for entry in entries:
            if entry["id"] == photo_id:
                continue
            distance = descriptors.histogram_distance(query_hist, descriptors.color_histogram(self.read_image(entry)))
            results.append((entry, float(distance)))
        return sorted(results, key=lambda pair: pair[1])
