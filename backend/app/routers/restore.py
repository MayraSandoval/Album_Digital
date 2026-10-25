from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Form, HTTPException

from app.album import Album
from app.config import MEDIA_URL, STORAGE_DIR
from app.gallery import Gallery
from app.schemas import ErrorOut, RestoreOut, StepOut
from album import RestorationOptions, RestorationPipeline, encode_png

router = APIRouter(prefix="/api/photos", tags=["restauración"])
album = Album(STORAGE_DIR)
gallery = Gallery(STORAGE_DIR)
pipeline = RestorationPipeline()

ERRORS = {404: {"model": ErrorOut}, 422: {"model": ErrorOut}, 501: {"model": ErrorOut}}

TRUE_VALUES = {"1", "true", "on", "yes"}


def _form_bool(value: str | None, default: bool) -> bool:
    """Form(bool) con default True se rompe en FastAPI 0.156 si el campo falta."""
    if value is None:
        return default
    return value.strip().lower() in TRUE_VALUES


@router.post(
    "/{photo_id}/restore",
    response_model=RestoreOut,
    summary="Restaurar una foto del álbum",
    responses=ERRORS,
)
async def restore_photo(
    photo_id: str,
    denoise: Annotated[str | None, Form(description="auto, median, bilateral o none")] = None,
    scratches: Annotated[str | None, Form(description="reparar rasguños")] = None,
    contrast: Annotated[str | None, Form(description="realzar contraste")] = None,
):
    entry = album.get(photo_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"No hay ninguna foto con id {photo_id}.")
    image = album.read_image(entry)
    options = RestorationOptions(
        denoise=denoise or "auto",  # type: ignore[arg-type]
        repair_scratches=_form_bool(scratches, default=True),
        contrast=_form_bool(contrast, default=True),
    )
    trace = pipeline.run(image, options)

    restored_url = None
    if any(r.status == "done" for r in trace.results):
        item = gallery.add_restored(
            entry["id"], encode_png(trace.image), trace.image.shape[1], trace.image.shape[0]
        )
        relative = f"{item['folder']}/{item['filename']}"
        album.mark_restored(entry, relative)
        restored_url = f"{MEDIA_URL}/{relative}"

    return RestoreOut(
        photo_id=photo_id,
        steps=[
            StepOut(number=r.step.number, name=r.step.name, label=r.step.label, status=r.status, message=r.message or None)
            for r in trace.results
        ],
        complete=trace.complete,
        original_url=f"{MEDIA_URL}/photos/{entry['filename']}",
        restored_url=restored_url,
    )
