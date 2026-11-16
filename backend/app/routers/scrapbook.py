from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response

from app.album import Album
from app.catalog import find, media_url
from app.config import STORAGE_DIR
from app.gallery import Gallery
from app.scrapbook import Scrapbook
from app.schemas import ErrorOut, ScrapbookOut, ScrapbookPhotoIn, ScrapbookPhotoOut

router = APIRouter(prefix="/api/scrapbook", tags=["álbum de recuerdos"])
album = Album(STORAGE_DIR)
gallery = Gallery(STORAGE_DIR)
scrapbook = Scrapbook(STORAGE_DIR)

ERRORS = {404: {"model": ErrorOut}, 409: {"model": ErrorOut}, 422: {"model": ErrorOut}}


def _photo_out(entry: dict) -> ScrapbookPhotoOut:
    return ScrapbookPhotoOut(
        id=entry["id"],
        name=entry["name"],
        kind=entry["source_kind"],
        source_id=entry["source_id"],
        width=entry["width"],
        height=entry["height"],
        added=entry["added"],
        url=f"/media/{entry['folder']}/{entry['filename']}",
    )


@router.get(
    "",
    response_model=ScrapbookOut,
    summary="El álbum de recuerdos: portada y fotos elegidas",
)
def get_scrapbook():
    data = scrapbook.all()
    return ScrapbookOut(photos=[_photo_out(entry) for entry in data["photos"]])


@router.post(
    "/photos",
    response_model=ScrapbookPhotoOut,
    status_code=201,
    summary="Sumar una foto de la galería al álbum, con un nombre para mostrar",
    responses=ERRORS,
)
def add_photo(payload: ScrapbookPhotoIn):
    item = find(album, gallery, payload.source_kind, payload.source_id)
    if item is None:
        raise HTTPException(
            status_code=404,
            detail=f"No hay ninguna imagen {payload.source_kind} con id {payload.source_id}.",
        )
    try:
        entry = scrapbook.add(
            payload.name,
            payload.source_kind,
            payload.source_id,
            item["folder"],
            item["filename"],
            item["width"],
            item["height"],
        )
    except ValueError:
        raise HTTPException(status_code=409, detail="Esa foto ya está en el álbum.") from None
    return _photo_out(entry)


@router.delete(
    "/photos/{item_id}",
    status_code=204,
    summary="Quitar una foto del álbum",
    responses={404: {"model": ErrorOut}},
)
def remove_photo(item_id: str):
    if not scrapbook.remove(item_id):
        raise HTTPException(status_code=404, detail=f"No hay ninguna foto con id {item_id} en el álbum.")
    return Response(status_code=204)


@router.delete(
    "",
    status_code=204,
    summary="Vaciar el álbum (las fotos siguen en la galería)",
)
def clear_scrapbook():
    scrapbook.clear()
    return Response(status_code=204)
