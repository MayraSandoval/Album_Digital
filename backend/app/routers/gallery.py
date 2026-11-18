from __future__ import annotations

import re
from typing import Literal

from fastapi import APIRouter, HTTPException, Response

from app.config import MEDIA_URL, PHOTOS_DIR, STORAGE_BACKEND
from app.gallery import RESTORED, RETRO, SCANNED
from app.schemas import ErrorOut, GalleryItemOut
from app.stores import album, gallery, scrapbook

router = APIRouter(prefix="/api/gallery", tags=["galería"])


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
    if STORAGE_BACKEND == "supabase" and any(
        item["kind"] == kind and item["id"] == item_id for item in gallery.all()
    ):
        scrapbook.remove_source(kind, item_id)
        if kind == RESTORED:
            album.clear_restored(item_id)

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
    if STORAGE_BACKEND == "local" and re.fullmatch(r"[0-9a-f]{12}", item_id):
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
