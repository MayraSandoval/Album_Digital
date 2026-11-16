from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from album import decode, descriptors
from app.album import Album
from app.catalog import ORIGINAL, catalog, media_url
from app.config import STORAGE_DIR
from app.gallery import Gallery
from app.schemas import ColorMatchOut, ErrorOut, SearchPhotoOut, SimilarMatchOut

router = APIRouter(prefix="/api/search", tags=["búsqueda"])
album = Album(STORAGE_DIR)
gallery = Gallery(STORAGE_DIR)

ERRORS = {422: {"model": ErrorOut}, 501: {"model": ErrorOut}}


def _parse_hex(hex_color: str) -> tuple[int, int, int]:
    value = hex_color.lstrip("#")
    if len(value) != 6:
        raise HTTPException(status_code=422, detail="El color debe ser un hexadecimal RRGGBB.")
    try:
        return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    except ValueError:
        raise HTTPException(status_code=422, detail="El color debe ser un hexadecimal RRGGBB.") from None


def _catalog() -> list[dict]:
    """Todas las imágenes de storage/: originales, digitalizadas, restauradas y retro."""
    return catalog(album, gallery)


def _read(item: dict):
    return decode((STORAGE_DIR / item["folder"] / item["filename"]).read_bytes())


def _match_out(item: dict) -> SearchPhotoOut:
    return SearchPhotoOut(
        id=item["id"],
        kind=item["kind"],
        width=item["width"],
        height=item["height"],
        created=item["created"],
        url=media_url(item),
        source_id=item.get("source_id"),
    )


@router.get(
    "/color",
    response_model=list[ColorMatchOut],
    summary="Buscar fotos por color en todo el almacenamiento (fracción de píxeles de ese color)",
    responses=ERRORS,
)
def search_by_color(
    hex: str = Query(description="Color objetivo, p. ej. C81E1E", pattern="^[0-9a-fA-F#]{6,7}$"),
    min: float = Query(0.05, ge=0.0, le=1.0, description="Fracción mínima de píxeles del color"),
):
    rgb = _parse_hex(hex)
    matches = []
    for item in _catalog():
        fraction = descriptors.color_fraction(_read(item), rgb)
        if fraction >= min:
            matches.append((item, float(fraction)))
    matches.sort(key=lambda pair: pair[1], reverse=True)
    return [ColorMatchOut(photo=_match_out(item), fraction=fraction) for item, fraction in matches]


@router.get(
    "/similar/{photo_id}",
    response_model=list[SimilarMatchOut],
    summary="Buscar fotos parecidas a una del álbum en todo el almacenamiento",
    responses={404: {"model": ErrorOut}, **ERRORS},
)
def search_similar(photo_id: str):
    query_entry = album.get(photo_id)
    if query_entry is None:
        raise HTTPException(status_code=404, detail=f"No hay ninguna foto con id {photo_id}.")

    items = _catalog()
    # La referencia es siempre el original; sus restauraciones y variantes retro
    # son imágenes distintas y sí pueden aparecer entre las parecidas.
    query = next(item for item in items if item["kind"] == ORIGINAL and item["id"] == photo_id)
    query_hist = descriptors.color_histogram(_read(query))

    results = []
    for item in items:
        if item["kind"] == ORIGINAL and item["id"] == photo_id:
            continue
        distance = descriptors.histogram_distance(query_hist, descriptors.color_histogram(_read(item)))
        results.append((item, float(distance)))
    results.sort(key=lambda pair: pair[1])
    return [SimilarMatchOut(photo=_match_out(item), distance=distance) for item, distance in results]
