from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, Response

from app.album import Album
from app.config import MEDIA_URL, PHOTOS_DIR, STORAGE_DIR
from app.gallery import RESTORED, SCANNED, Gallery
from app.schemas import ErrorOut, GalleryItemOut

router = APIRouter(prefix="/api/gallery", tags=["galería"])
gallery = Gallery(STORAGE_DIR)
album = Album(STORAGE_DIR)


def _item_out(entry: dict) -> GalleryItemOut:
    return GalleryItemOut(
        id=entry["id"],
        kind=entry["kind"],
        width=entry["width"],
        height=entry["height"],
        created=entry["created"],
        source_id=entry.get("source_id"),
        url=f"{MEDIA_URL}/{entry['folder']}/{entry['filename']}",
    )


def _legacy_restored() -> list[dict]:
    """Restauraciones anteriores a storage/restored/: el PNG quedó en photos/."""
    saved_sources = {e.get("source_id") for e in gallery.all() if e.get("kind") == RESTORED}
    items = []
    for entry in album.all():
        if not entry.get("restored") or entry["id"] in saved_sources:
            continue
        path = PHOTOS_DIR / f"{entry['id']}_restored.png"
        if not path.exists():
            continue
        created = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
        items.append(
            {
                "id": entry["id"],
                "kind": RESTORED,
                "folder": "photos",
                "filename": path.name,
                "width": entry["width"],
                "height": entry["height"],
                "created": created,
                "source_id": entry["id"],
            }
        )
    return items


@router.get(
    "",
    response_model=list[GalleryItemOut],
    summary="Galería: fotos digitalizadas y restauradas",
)
def list_gallery():
    items = [_item_out(entry) for entry in gallery.all() + _legacy_restored()]
    return sorted(items, key=lambda item: item.created, reverse=True)


@router.delete(
    "/{kind}/{item_id}",
    status_code=204,
    summary="Eliminar una foto de la galería (no borra la foto original)",
    responses={404: {"model": ErrorOut}},
)
def delete_gallery_item(kind: Literal["scanned", "restored"], item_id: str):
    if kind == SCANNED:
        if not gallery.remove_scanned(item_id):
            raise HTTPException(
                status_code=404, detail=f"No hay ninguna foto digitalizada con id {item_id} en la galería."
            )
        return Response(status_code=204)

    removed = gallery.remove_restored(item_id)
    legacy = PHOTOS_DIR / f"{item_id}_restored.png"
    if legacy.exists():
        legacy.unlink()
        removed = True
    if not removed:
        raise HTTPException(
            status_code=404, detail=f"No hay ninguna foto restaurada con id {item_id} en la galería."
        )
    album.clear_restored(item_id)
    return Response(status_code=204)
