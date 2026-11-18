from __future__ import annotations

import math
from typing import Annotated, Literal

from fastapi import APIRouter, Form, HTTPException

from app.config import MEDIA_URL, PHOTOS_DIR, STORAGE_BACKEND, STORAGE_DIR
from app.schemas import (
    AppliedPresetStepOut,
    ContrastIn,
    DenoiseIn,
    ErrorOut,
    ManualRestoreOut,
    PresetApplyOut,
    RestoreMetricsOut,
    RestoreOut,
    ScratchRepairIn,
    SharpenIn,
    StepOut,
    WhiteBalanceIn,
)
from app.steps import build_step
from app.stores import album, gallery, presets, read_media
from album import RestorationOptions, RestorationPipeline, decode, encode_png
from album.quality import diagnose, mse, psnr

router = APIRouter(prefix="/api/photos", tags=["restauración"])
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
    if STORAGE_BACKEND == "supabase":
        restored = next(
            (item for item in gallery.all() if item["kind"] == "restored" and item["source_id"] == entry["id"]),
            None,
        )
        if restored is not None:
            data = read_media(restored["folder"], restored["filename"])
            if data is None:
                raise FileNotFoundError("No se encontró la imagen restaurada.")
            return decode(data)
    else:
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
    parameters = params.model_dump()
    return _apply_step(entry, build_step("denoise", parameters), "denoise", parameters)


@router.post(
    "/{photo_id}/restore/scratches",
    response_model=ManualRestoreOut,
    summary="Paso manual: reparar rasguños (top-hat + inpainting)",
    responses=ERRORS,
)
def restore_scratches(photo_id: str, params: ScratchRepairIn):
    entry = _photo(photo_id)
    parameters = params.model_dump()
    return _apply_step(entry, build_step("scratches", parameters), "scratches", parameters)


@router.post(
    "/{photo_id}/restore/contrast",
    response_model=ManualRestoreOut,
    summary="Paso manual: realzar contraste (CLAHE)",
    responses=ERRORS,
)
def restore_contrast(photo_id: str, params: ContrastIn):
    entry = _photo(photo_id)
    parameters = params.model_dump()
    return _apply_step(entry, build_step("contrast", parameters), "contrast", parameters)


@router.post(
    "/{photo_id}/restore/whitebalance",
    response_model=ManualRestoreOut,
    summary="Paso manual: balance de blancos y estiramiento del histograma",
    responses=ERRORS,
)
def restore_white_balance(photo_id: str, params: WhiteBalanceIn):
    entry = _photo(photo_id)
    parameters = params.model_dump()
    return _apply_step(entry, build_step("whitebalance", parameters), "whitebalance", parameters)


@router.post(
    "/{photo_id}/restore/sharpen",
    response_model=ManualRestoreOut,
    summary="Paso manual: realzar nitidez (unsharp mask)",
    responses=ERRORS,
)
def restore_sharpen(photo_id: str, params: SharpenIn):
    entry = _photo(photo_id)
    parameters = params.model_dump()
    return _apply_step(entry, build_step("sharpen", parameters), "sharpen", parameters)


@router.post(
    "/{photo_id}/restore/preset/{preset_id}",
    response_model=PresetApplyOut,
    summary="Aplicar una configuración guardada sobre el resultado actual",
    responses=ERRORS,
)
def restore_with_preset(photo_id: str, preset_id: str):
    entry = _photo(photo_id)
    preset = presets.get(preset_id)
    if preset is None:
        raise HTTPException(status_code=404, detail=f"No hay ninguna configuración con id {preset_id}.")

    steps = [build_step(item["operation"], item["parameters"]) for item in preset["steps"]]
    trace = pipeline.run(_current_image(entry), steps=steps)
    for result in trace.results:
        if result.status != "done" or result.image is None:
            raise HTTPException(
                status_code=422,
                detail=result.message or f"No se pudo aplicar el paso {result.step.label}.",
            )

    image = trace.image
    item = gallery.add_restored(entry["id"], encode_png(image), image.shape[1], image.shape[0])
    relative = f"{item['folder']}/{item['filename']}"
    album.mark_restored(entry, relative)
    return PresetApplyOut(
        photo_id=entry["id"],
        preset_id=preset["id"],
        preset_name=preset["name"],
        steps=[
            AppliedPresetStepOut(operation=spec["operation"], label=step.label, parameters=spec["parameters"])
            for spec, step in zip(preset["steps"], steps)
        ],
        width=int(image.shape[1]),
        height=int(image.shape[0]),
        original_url=f"{MEDIA_URL}/photos/{entry['filename']}",
        restored_url=f"{MEDIA_URL}/{relative}",
        metrics=_compare(album.read_image(entry), image),
    )
