"""Armado de los pasos de restauración desde los parámetros de la API.

Los endpoints manuales y las configuraciones guardadas usan la misma receta:
primero se validan los parámetros con el schema de la operación y después se
construye el paso del core.
"""

from __future__ import annotations

from album.pipeline import Step
from album.restoration import ContrastStep, DenoiseStep, ScratchRepairStep, SharpenStep, WhiteBalanceStep
from app.schemas import STEP_MODELS, StepOperation


def build_step(operation: StepOperation, parameters: dict) -> Step:
    data = STEP_MODELS[operation].model_validate(parameters)
    if operation == "denoise":
        return DenoiseStep(
            method=data.method,
            kernel_size=data.kernel_size,
            diameter=data.diameter,
            sigma=data.sigma,
        )
    if operation == "scratches":
        return ScratchRepairStep(
            length=data.length,
            min_contrast=data.min_contrast,
            radius=data.radius,
            method=data.method,
        )
    if operation == "contrast":
        return ContrastStep(clip_limit=data.clip_limit, tile_grid=(data.tile_size, data.tile_size))
    if operation == "whitebalance":
        return WhiteBalanceStep(method=data.method, stretch=data.stretch)
    if operation == "sharpen":
        return SharpenStep(amount=data.amount, sigma=data.sigma)
    raise ValueError(f"operación de restauración desconocida: {operation}")
