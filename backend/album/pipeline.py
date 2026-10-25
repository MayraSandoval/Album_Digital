"""El pipeline de restauración: arma la lista de pasos y los corre.

    foto dañada → DenoiseStep → ScratchRepairStep → ContrastStep

Reglas (las chequean los tests de test_restoration.py):
  - un paso que lanza NotImplementedYet se saltea ("pending"): la foto
    sigue igual y la aplicación sigue funcionando;
  - un paso que lanza otra excepción o devuelve algo que no es una imagen
    válida queda "failed" y los siguientes no corren ("blocked");
  - ningún paso puede cambiar el tamaño de la foto: todos devuelven una
    imagen (alto, ancho, 3) uint8 de las mismas dimensiones que recibieron.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar, Literal

import numpy as np

from album.exceptions import AlbumError, NotImplementedYet

log = logging.getLogger("album")

DenoiseMethod = Literal["auto", "median", "bilateral", "none"]
Status = Literal["done", "pending", "blocked", "failed"]


class Step(ABC):
    """Un paso del pipeline.

    Interfaz: `apply(image)` recibe una imagen y devuelve una NUEVA (sin
    modificar la que recibe).
    """

    number: ClassVar[int | None] = None  # número de paso en la consigna (None: dado)
    name: ClassVar[str]                  # id usado por la API: "denoise"
    label: ClassVar[str]                 # nombre mostrado en el frontend: "Quitar ruido"

    @abstractmethod
    def apply(self, image: np.ndarray) -> np.ndarray:
        """Devuelve una NUEVA imagen con el paso aplicado."""

    def __repr__(self) -> str:
        return f"{type(self).__name__}()"


@dataclass(frozen=True)
class RestorationOptions:
    """Qué se le pide al pipeline."""

    denoise: DenoiseMethod = "auto"      # "none" desactiva el paso
    repair_scratches: bool = True
    contrast: bool = True


@dataclass(frozen=True)
class StepResult:
    step: Step
    status: Status
    image: np.ndarray | None = None  # lo que devolvió el paso (solo si "done")
    message: str = ""                # por qué falló o se bloqueó


@dataclass(frozen=True)
class Trace:
    """Lo que pasó en cada paso de una corrida."""

    photo: np.ndarray
    results: list[StepResult]

    @property
    def image(self) -> np.ndarray:
        """La última imagen producida: la foto restaurada si todo salió bien."""
        done = [r.image for r in self.results if r.status == "done"]
        return done[-1] if done else self.photo

    @property
    def complete(self) -> bool:
        """True si hubo pasos y todos terminaron."""
        return bool(self.results) and all(r.status == "done" for r in self.results)

    @property
    def failure(self) -> StepResult | None:
        """El primer paso que falló, si hay alguno."""
        return next((r for r in self.results if r.status == "failed"), None)


class RestorationPipeline:
    """Corre los pasos de restauración sobre una foto."""

    def steps_for(self, options: RestorationOptions) -> list[Step]:
        # Import acá para evitar el ciclo album.pipeline ↔ album.restoration.
        from album.restoration import ContrastStep, DenoiseStep, ScratchRepairStep

        steps: list[Step] = []
        if options.denoise != "none":
            steps.append(DenoiseStep(method=options.denoise))
        if options.repair_scratches:
            steps.append(ScratchRepairStep())
        if options.contrast:
            steps.append(ContrastStep())
        return steps

    def run(
        self,
        image: np.ndarray,
        options: RestorationOptions | None = None,
        steps: list[Step] | None = None,
    ) -> Trace:
        """Restaura `image` y devuelve el Trace con el detalle de cada paso.

        `steps` permite inyectar pasos propios (lo usan los tests); por
        defecto se arma la lista con `steps_for(options)`.
        """
        if steps is None:
            steps = self.steps_for(options or RestorationOptions())
        results: list[StepResult] = []
        current = image
        for step in steps:
            if any(r.status == "failed" for r in results):
                results.append(StepResult(step, "blocked", None, "un paso anterior falló"))
                continue
            try:
                out = step.apply(current)
            except NotImplementedYet:
                results.append(StepResult(step, "pending"))
                continue
            except AlbumError as exc:
                log.warning("paso %s falló: %s", step.name, exc)
                results.append(StepResult(step, "failed", None, str(exc)))
                continue
            except Exception as exc:  # errores de cv2/numpy y demás
                log.warning("paso %s falló: %s: %s", step.name, type(exc).__name__, exc)
                results.append(StepResult(step, "failed", None, f"{type(exc).__name__}: {exc}"))
                continue
            if not _same_shape(out, current):
                results.append(StepResult(step, "failed", None, "cambió el tamaño de la imagen"))
                continue
            results.append(StepResult(step, "done", image=out))
            current = out
        return Trace(photo=image, results=results)


def _same_shape(a: np.ndarray, b: np.ndarray) -> bool:
    return (
        isinstance(a, np.ndarray)
        and a.ndim == 3
        and a.shape[2] == 3
        and a.dtype == np.uint8
        and a.shape == b.shape
    )
