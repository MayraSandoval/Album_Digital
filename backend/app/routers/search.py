from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.album import Album
from app.config import STORAGE_DIR
from app.routers.photos import _photo_out
from app.schemas import ColorMatchOut, ErrorOut, SimilarMatchOut

router = APIRouter(prefix="/api/search", tags=["búsqueda"])
album = Album(STORAGE_DIR)

ERRORS = {422: {"model": ErrorOut}, 501: {"model": ErrorOut}}


def _parse_hex(hex_color: str) -> tuple[int, int, int]:
    value = hex_color.lstrip("#")
    if len(value) != 6:
        raise HTTPException(status_code=422, detail="El color debe ser un hexadecimal RRGGBB.")
    try:
        return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    except ValueError:
        raise HTTPException(status_code=422, detail="El color debe ser un hexadecimal RRGGBB.") from None


@router.get(
    "/color",
    response_model=list[ColorMatchOut],
    summary="Buscar fotos por color (fracción de píxeles de ese color)",
    responses=ERRORS,
)
def search_by_color(
    hex: str = Query(description="Color objetivo, p. ej. C81E1E", pattern="^[0-9a-fA-F#]{6,7}$"),
    min: float = Query(0.05, ge=0.0, le=1.0, description="Fracción mínima de píxeles del color"),
):
    rgb = _parse_hex(hex)
    matches = album.search_by_color(rgb, min)
    return [ColorMatchOut(photo=_photo_out(entry), fraction=fraction) for entry, fraction in matches]


@router.get(
    "/similar/{photo_id}",
    response_model=list[SimilarMatchOut],
    summary="Buscar fotos parecidas a una del álbum (distancia de histograma)",
    responses={404: {"model": ErrorOut}, **ERRORS},
)
def search_similar(photo_id: str):
    if album.get(photo_id) is None:
        raise HTTPException(status_code=404, detail=f"No hay ninguna foto con id {photo_id}.")
    matches = album.search_similar(photo_id)
    return [SimilarMatchOut(photo=_photo_out(entry), distance=distance) for entry, distance in matches]
