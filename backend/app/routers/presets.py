from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.config import STORAGE_DIR
from app.presets import PresetStore
from app.schemas import ErrorOut, PresetIn, PresetOut

router = APIRouter(prefix="/api/presets", tags=["restauración"])
store = PresetStore(STORAGE_DIR)

ERRORS = {404: {"model": ErrorOut}, 422: {"model": ErrorOut}}


@router.get(
    "",
    response_model=list[PresetOut],
    summary="Listar las configuraciones de restauración guardadas",
)
def list_presets():
    return store.all()


@router.post(
    "",
    response_model=PresetOut,
    summary="Guardar una configuración con el nombre elegido",
    responses=ERRORS,
)
def save_preset(body: PresetIn):
    """Si ya existe una configuración con ese nombre, se actualiza."""
    return store.save(body.name, [step.model_dump() for step in body.steps])


@router.delete(
    "/{preset_id}",
    status_code=204,
    summary="Borrar una configuración guardada",
    responses=ERRORS,
)
def delete_preset(preset_id: str):
    if not store.delete(preset_id):
        raise HTTPException(status_code=404, detail=f"No hay ninguna configuración con id {preset_id}.")
