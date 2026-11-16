from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Response

from app.album import Album
from app.config import MEDIA_URL, PHOTOS_DIR, STORAGE_DIR
from app.gallery import RESTORED, RETRO, SCANNED, Gallery
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


@router.get(
    "",
    response_model=list[GalleryItemOut],
    summary="Galería: fotos digitalizadas, restauradas y con estilo retro",
)
def list_gallery():
    items = [_item_out(entry) for entry in gallery.all_with_legacy(album.all())]
    return sorted(items, key=lambda item: item.created, reverse=True)


@router.delete(
    "/{kind}/{item_id}",
    status_code=204,
    summary="Eliminar una foto de la galería (no borra la foto original)",
    responses={404: {"model": ErrorOut}},
)
def delete_gallery_item(kind: Literal["scanned", "restored", "retro"], item_id: str):
    if kind == SCANNED:
        if not gallery.remove_scanned(item_id):
            raise HTTPException(
                status_code=404, detail=f"No hay ninguna foto digitalizada con id {item_id} en la galería."
            )
        return Response(status_code=204)

    if kind == RETRO:
        if not gallery.remove_retro_item(item_id):
            raise HTTPException(
                status_code=404, detail=f"No hay ninguna foto con estilo retro e id {item_id} en la galería."
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
