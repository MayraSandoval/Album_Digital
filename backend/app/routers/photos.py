from __future__ import annotations

from fastapi import APIRouter, HTTPException, UploadFile

from app.album import Album
from app.config import MEDIA_URL, PHOTOS_DIR, STORAGE_DIR
from app.schemas import ErrorOut, PhotoOut
from app.uploads import read_upload

router = APIRouter(prefix="/api/photos", tags=["fotos"])
album = Album(STORAGE_DIR)

ERRORS = {400: {"model": ErrorOut}, 422: {"model": ErrorOut}, 501: {"model": ErrorOut}}


def _photo_out(entry: dict) -> PhotoOut:
    restored_url = f"{MEDIA_URL}/photos/{entry['id']}_restored.png" if entry.get("restored") else None
    return PhotoOut(
        id=entry["id"],
        width=entry["width"],
        height=entry["height"],
        mode=entry["mode"],
        size_bytes=entry["size_bytes"],
        restored=entry.get("restored", False),
        created=entry["created"],
        duplicates=[d["id"] for d in album.duplicates_of(entry)],
        url=f"{MEDIA_URL}/photos/{entry['filename']}",
        restored_url=restored_url,
    )


@router.post("", response_model=PhotoOut, status_code=201, summary="Subir una foto al álbum", responses=ERRORS)
async def upload_photo(file: UploadFile):
    """La guarda, calcula su hash perceptual y avisa si ya existía (duplicado)."""
    data = await read_upload(file)
    entry = album.add(data)
    return _photo_out(entry)


@router.get("", response_model=list[PhotoOut], summary="Listar el álbum")
def list_photos():
    return [_photo_out(e) for e in album.all()]


@router.get("/{photo_id}", response_model=PhotoOut, summary="Detalle de una foto", responses={404: {"model": ErrorOut}})
def get_photo(photo_id: str):
    entry = album.get(photo_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"No hay ninguna foto con id {photo_id}.")
    return _photo_out(entry)


@router.delete("/{photo_id}", status_code=204, summary="Borrar una foto", responses={404: {"model": ErrorOut}})
def delete_photo(photo_id: str):
    if not album.delete(photo_id):
        raise HTTPException(status_code=404, detail=f"No hay ninguna foto con id {photo_id}.")


_ = PHOTOS_DIR  # se usa vía Album; import explícito para que aparezca en el namespace
