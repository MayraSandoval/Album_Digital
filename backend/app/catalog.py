"""Catálogo de las imágenes que viven en storage/.

Reúne los originales del álbum y los resultados de la galería (digitalizadas,
restauradas y retro) con una forma común: id, kind, folder, filename, etc.
Lo usan la búsqueda y el álbum de recuerdos.
"""

from __future__ import annotations

from app.album import Album
from app.config import MEDIA_URL
from app.gallery import Gallery

ORIGINAL = "original"


def catalog(album: Album, gallery: Gallery) -> list[dict]:
    originals = [{**entry, "kind": ORIGINAL, "folder": "photos"} for entry in album.all()]
    return originals + gallery.all_with_legacy(album.all())


def find(album: Album, gallery: Gallery, kind: str, item_id: str) -> dict | None:
    return next(
        (item for item in catalog(album, gallery) if item["kind"] == kind and item["id"] == item_id),
        None,
    )


def media_url(item: dict) -> str:
    return f"{MEDIA_URL}/{item['folder']}/{item['filename']}"
