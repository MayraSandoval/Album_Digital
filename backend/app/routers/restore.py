from __future__ import annotations

import math
from typing import Annotated, Literal

from fastapi import APIRouter, Form, HTTPException

from app.album import Album
from app.config import MEDIA_URL, PHOTOS_DIR, STORAGE_DIR
from app.gallery import Gallery
from app.schemas import (
    ContrastIn,
    DenoiseIn,
    ErrorOut,
    ManualRestoreOut,
    RestoreMetricsOut,
    RestoreOut,
    ScratchRepairIn,
    SharpenIn,
    StepOut,
    WhiteBalanceIn,
)
from album import RestorationOptions, RestorationPipeline, decode, encode_png
from album.quality import diagnose, mse, psnr
from album.restoration import (
    ContrastStep,
    DenoiseStep,
    ScratchRepairStep,
    SharpenStep,
    WhiteBalanceStep,
)

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


def _photo(photo_id: str) -> dict:
    entry = album.get(photo_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"No hay ninguna foto con id {photo_id}.")
    return entry


def _current_image(entry: dict):
    """El paso manual trabaja sobre el último resultado, no sobre el original."""
    restored = STORAGE_DIR / "restored" / f"{entry['id']}.png"
    if restored.exists():
        return decode(restored.read_bytes())
    legacy = PHOTOS_DIR / f"{entry['id']}_restored.png"
    if legacy.exists():
        return decode(legacy.read_bytes())
    return album.read_image(entry)


def _compare(original, image) -> RestoreMetricsOut:
    """Métricas de la restauración contra el original: nitidez, ruido y PSNR."""
    before = diagnose(original)
    after = diagnose(image)
    value = psnr(original, image)
    return RestoreMetricsOut(
        sharpness_before=before.sharpness,
        sharpness_after=after.sharpness,
        noise_before=before.noise,
        noise_after=after.noise,
        mse=mse(original, image),
        psnr=value if math.isfinite(value) else None,
    )


def _apply_step(
    entry: dict,
    step,
    operation: Literal["denoise", "scratches", "contrast", "whitebalance", "sharpen"],
    parameters: dict,
) -> ManualRestoreOut:
    trace = pipeline.run(_current_image(entry), steps=[step])
    result = trace.results[0]
    if result.status != "done" or result.image is None:
        raise HTTPException(
            status_code=422,
            detail=result.message or f"No se pudo aplicar el paso {step.label}.",
        )

    image = result.image
    item = gallery.add_restored(entry["id"], encode_png(image), image.shape[1], image.shape[0])
    relative = f"{item['folder']}/{item['filename']}"
    album.mark_restored(entry, relative)
    return ManualRestoreOut(
        photo_id=entry["id"],
        operation=operation,
        label=step.label,
        parameters=parameters,
        width=int(image.shape[1]),
        height=int(image.shape[0]),
        original_url=f"{MEDIA_URL}/photos/{entry['filename']}",
        restored_url=f"{MEDIA_URL}/{relative}",
        metrics=_compare(album.read_image(entry), image),
    )


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
    entry = _photo(photo_id)
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


@router.post(
    "/{photo_id}/restore/denoise",
    response_model=ManualRestoreOut,
    summary="Paso manual: quitar ruido (mediana o bilateral)",
    responses=ERRORS,
)
def restore_denoise(photo_id: str, params: DenoiseIn):
    entry = _photo(photo_id)
    step = DenoiseStep(
        method=params.method,
        kernel_size=params.kernel_size,
        diameter=params.diameter,
        sigma=params.sigma,
    )
    return _apply_step(entry, step, "denoise", params.model_dump())


@router.post(
    "/{photo_id}/restore/scratches",
    response_model=ManualRestoreOut,
    summary="Paso manual: reparar rasguños (top-hat + inpainting)",
    responses=ERRORS,
)
def restore_scratches(photo_id: str, params: ScratchRepairIn):
    entry = _photo(photo_id)
    step = ScratchRepairStep(
        length=params.length,
        min_contrast=params.min_contrast,
        radius=params.radius,
        method=params.method,
    )
    return _apply_step(entry, step, "scratches", params.model_dump())


@router.post(
    "/{photo_id}/restore/contrast",
    response_model=ManualRestoreOut,
    summary="Paso manual: realzar contraste (CLAHE)",
    responses=ERRORS,
)
def restore_contrast(photo_id: str, params: ContrastIn):
    entry = _photo(photo_id)
    step = ContrastStep(
        clip_limit=params.clip_limit,
        tile_grid=(params.tile_size, params.tile_size),
    )
    return _apply_step(entry, step, "contrast", params.model_dump())


@router.post(
    "/{photo_id}/restore/whitebalance",
    response_model=ManualRestoreOut,
    summary="Paso manual: balance de blancos y estiramiento del histograma",
    responses=ERRORS,
)
def restore_white_balance(photo_id: str, params: WhiteBalanceIn):
    entry = _photo(photo_id)
    step = WhiteBalanceStep(method=params.method, stretch=params.stretch)
    return _apply_step(entry, step, "whitebalance", params.model_dump())


@router.post(
    "/{photo_id}/restore/sharpen",
    response_model=ManualRestoreOut,
    summary="Paso manual: realzar nitidez (unsharp mask)",
    responses=ERRORS,
)
def restore_sharpen(photo_id: str, params: SharpenIn):
    entry = _photo(photo_id)
    step = SharpenStep(amount=params.amount, sigma=params.sigma)
    return _apply_step(entry, step, "sharpen", params.model_dump())
