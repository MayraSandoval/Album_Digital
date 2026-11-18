from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Form, HTTPException

from app.config import MEDIA_URL
from app.schemas import ErrorOut, PaletteOut, RetroOut
from app.stores import album, gallery
from album import PALETTES, RetroOptions, apply_retro, encode_png
from album.retro import DEFAULT_PALETTE, UnknownPalette

router = APIRouter(prefix="/api", tags=["estilo retro"])

ERRORS = {404: {"model": ErrorOut}, 422: {"model": ErrorOut}, 501: {"model": ErrorOut}}
TRUE_VALUES = {"1", "true", "on", "yes"}


def _form_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in TRUE_VALUES


@router.get(
    "/retro/palettes",
    response_model=list[PaletteOut],
    summary="Paletas disponibles para el estilo retro",
)
def list_retro_palettes():
    return [
        PaletteOut(
            name=palette.name,
            label=palette.label,
            colors=list(palette.hex_colors),
            monochrome=palette.monochrome,
        )
        for palette in PALETTES.values()
    ]


@router.post(
    "/photos/{photo_id}/retro",
    response_model=RetroOut,
    summary="Aplicar un estilo retro a una foto del álbum",
    responses=ERRORS,
)
async def apply_photo_retro(
    photo_id: str,
    palette: Annotated[str | None, Form(description="gameboy, bw, virtualboy, cga o pico8")] = None,
    dithering: Annotated[str | None, Form(description="dithering Floyd–Steinberg")] = None,
):
    entry = album.get(photo_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"No hay ninguna foto con id {photo_id}.")

    options = RetroOptions(
        palette=(palette or DEFAULT_PALETTE).strip().lower(),
        dithering=_form_bool(dithering, default=RetroOptions().dithering),
    )
    try:
        retro_image = apply_retro(album.read_image(entry), options)
    except UnknownPalette as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    item = gallery.add_retro(
        entry["id"],
        encode_png(retro_image),
        retro_image.shape[1],
        retro_image.shape[0],
        options.palette,
        options.dithering,
    )
    selected = PALETTES[options.palette]
    return RetroOut(
        photo_id=photo_id,
        palette=selected.name,
        palette_label=selected.label,
        dithering=options.dithering,
        width=retro_image.shape[1],
        height=retro_image.shape[0],
        original_url=f"{MEDIA_URL}/photos/{entry['filename']}",
        url=f"{MEDIA_URL}/{item['folder']}/{item['filename']}",
    )
