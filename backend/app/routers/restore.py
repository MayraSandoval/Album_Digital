from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Form, HTTPException

from app.album import Album
from app.config import MEDIA_URL, STORAGE_DIR
from app.schemas import ErrorOut, RestoreOut, StepOut
from album import RestorationOptions, RestorationPipeline

router = APIRouter(prefix="/api/photos", tags=["restauración"])
album = Album(STORAGE_DIR)
pipeline = RestorationPipeline()

ERRORS = {404: {"model": ErrorOut}, 422: {"model": ErrorOut}, 501: {"model": ErrorOut}}


@router.post(
    "/{photo_id}/restore",
    response_model=RestoreOut,
    summary="Restaurar una foto del álbum",
    responses=ERRORS,
)
async def restore_photo(
    photo_id: str,
    denoise: Annotated[str, Form(description="auto, median, bilateral o none")] = "auto",
    scratches: Annotated[bool, Form(description="reparar rasguños")] = True,
    contrast: Annotated[bool, Form(description="realzar contraste")] = True,
):
    entry = album.get(photo_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"No hay ninguna foto con id {photo_id}.")
    image = album.read_image(entry)
    options = RestorationOptions(denoise=denoise, repair_scratches=scratches, contrast=contrast)  # type: ignore[arg-type]
    trace = pipeline.run(image, options)

    restored_url = None
    if any(r.status == "done" for r in trace.results):
        album.mark_restored(entry, trace.image)
        restored_url = f"{MEDIA_URL}/photos/{entry['id']}_restored.png"

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
