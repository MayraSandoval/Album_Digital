from __future__ import annotations

from fastapi import APIRouter, Response, UploadFile

from app.schemas import ErrorOut
from app.stores import gallery
from app.uploads import read_upload
from album import decode, encode_png, limit_side
from album.scanning import Scanner

router = APIRouter(prefix="/api", tags=["digitalización"])

ERRORS = {400: {"model": ErrorOut}, 422: {"model": ErrorOut}, 501: {"model": ErrorOut}}


@router.post(
    "/scan",
    response_class=Response,
    summary="Digitalizar la foto de una foto impresa (PNG enderezado)",
    responses={200: {"content": {"image/png": {}}, "description": "La foto enderezada"}, **ERRORS},
)
async def scan(file: UploadFile):
    """Detecta la hoja, corrige la perspectiva y devuelve el PNG resultante.

    DocumentNotFound → 422 si no encuentra ninguna hoja.
    El resultado también queda guardado en storage/scanned/ para la galería.
    """
    data = await read_upload(file)
    image = limit_side(decode(data))
    warped = limit_side(Scanner().scan(image), max_side=1000)
    png = encode_png(warped)
    gallery.add_scanned(png, warped.shape[1], warped.shape[0])
    return Response(png, media_type="image/png")
