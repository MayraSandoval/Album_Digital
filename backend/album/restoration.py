"""Parte 2: los pasos de restauración.

Cada paso es una clase con la interfaz `Step` (de album/pipeline.py): `apply`
recibe una imagen y devuelve una NUEVA, sin modificar la que recibe y sin
cambiar su tamaño. El pipeline los corre en este orden:

    foto dañada → DenoiseStep → ScratchRepairStep → ContrastStep

"""

from __future__ import annotations

import cv2
import numpy as np

from album.pipeline import DenoiseMethod, Step
from album.quality import diagnose

MEDIAN_KERNEL = 5              # ventana del filtro de mediana (impar)
BILATERAL_DIAMETER = 5         # vecindad del filtro bilateral
BILATERAL_SIGMA = 75.0         # sigmaColor = sigmaSpace
SALT_PEPPER_FRACTION = 0.01    # % de píxeles extremos que delata sal y pimienta

SCRATCH_LENGTH = 25            # largo del kernel alargado del top-hat
SCRATCH_MIN_CONTRAST = 40      # umbral Otsu mínimo para creer que hay rayas
SCRATCH_MAX_FRACTION = 0.05    # si la máscara cubre más, es textura y no rayas
INPAINT_RADIUS = 3

CLAHE_CLIP_LIMIT = 2.5  # 2.0 (notebook) no llegaba a 1.3× en el sintético; 2.5 sí
CLAHE_TILE_GRID = (8, 8)


class DenoiseStep(Step):
    """Paso 1: quitar el ruido.

    Con method="auto" decide solo usando quality.diagnose:
      - (píxeles sueltos al 0 o al 255) → filtro de
        mediana (cv2.medianBlur, kernel impar chico, 3 o 5);
      - ruido fino gaussiano → filtro bilateral (preserva bordes mejor que
        el gaussiano: comparalo en el informe, es un experimento directo).
    Con "median" o "bilateral" no diagnostica: aplica ese filtro y listo.
    """

    number = 1
    name = "denoise"
    label = "Quitar ruido"

    def __init__(self, method: DenoiseMethod = "auto") -> None:
        self.method = method

    def __repr__(self) -> str:
        return f"{type(self).__name__}(method={self.method!r})"

    def apply(self, image: np.ndarray) -> np.ndarray:
        method = self.method
        if method == "auto":
            if not diagnose(image).noisy:
                return image.copy()  # no hay ruido que sacar
            method = "median" if _extreme_fraction(image) > SALT_PEPPER_FRACTION else "bilateral"

        if method == "median":
            return cv2.medianBlur(image, MEDIAN_KERNEL)
        if method == "bilateral":
            return cv2.bilateralFilter(
                image, BILATERAL_DIAMETER, BILATERAL_SIGMA, BILATERAL_SIGMA
            )
        return image.copy()


def _extreme_fraction(image: np.ndarray) -> float:
    """Fracción de píxeles casi negros o casi blancos (sal y pimienta)."""
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    return float(((gray <= 10) | (gray >= 245)).mean())


class ScratchRepairStep(Step):
    """Paso 2: tapar rasguños.

      1. detectá las rayas claras y finas con un top-hat blanco
         (cv2.morphologyEx con MORPH_TOPHAT) y un kernel alargado
         (cv2.getStructuringElement con forma RECT de, p. ej., 25×1 para
         rayas horizontales; probá también 1×25 para verticales);
      2. umbralizá el top-hat para quedarte con una máscara de los daños
         (cv2.threshold con un valor alto, o directamente Otsu);
      3. rellená con cv2.inpaint usando Inpainting TELEA o NS.
    """

    number = 2
    name = "scratch_repair"
    label = "Reparar rasguños"

    def __init__(self, radius: int = INPAINT_RADIUS, flags: int = cv2.INPAINT_TELEA) -> None:
        self.radius = radius
        self.flags = flags

    def __repr__(self) -> str:
        return f"{type(self).__name__}(radius={self.radius!r}, flags={self.flags!r})"

    def apply(self, image: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        horizontal = cv2.getStructuringElement(cv2.MORPH_RECT, (SCRATCH_LENGTH, 1))
        vertical = cv2.getStructuringElement(cv2.MORPH_RECT, (1, SCRATCH_LENGTH))

        # Una raya clara y fina no sobrevive a la apertura con un kernel
        # perpendicular a su dirección: queda en el top-hat.
        top_hat = cv2.max(
            cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, horizontal),
            cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, vertical),
        )

        threshold, _ = cv2.threshold(top_hat, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        if threshold < SCRATCH_MIN_CONTRAST:
            return image.copy()  # Otsu separó textura o grano, no rayas

        _, mask = cv2.threshold(top_hat, threshold, 255, cv2.THRESH_BINARY)
        mask = cv2.dilate(mask, np.ones((3, 3), np.uint8), iterations=1)
        if np.count_nonzero(mask) / mask.size > SCRATCH_MAX_FRACTION:
            return image.copy()  # demasiado "daño" para ser rasguños finos

        return cv2.inpaint(image, mask, self.radius, self.flags)


class ContrastStep(Step):
    """Paso 3: realce de contraste local.

    CLAHE sobre el canal de luminancia (pasá a LAB con
    cv2.COLOR_RGB2LAB, realzá el canal L con cv2.createCLAHE y volvé a RGB)
    para aclarar sombras sin quemar las luces (clipLimit y tileGridSize).
    """

    number = 3
    name = "contrast"
    label = "Realzar contraste"

    def __init__(
        self,
        clip_limit: float = CLAHE_CLIP_LIMIT,
        tile_grid: tuple[int, int] = CLAHE_TILE_GRID,
    ) -> None:
        self.clip_limit = clip_limit
        self.tile_grid = tile_grid

    def __repr__(self) -> str:
        return f"{type(self).__name__}(clip_limit={self.clip_limit!r}, tile_grid={self.tile_grid!r})"

    def apply(self, image: np.ndarray) -> np.ndarray:
        lightness, a, b = cv2.split(cv2.cvtColor(image, cv2.COLOR_RGB2LAB))
        clahe = cv2.createCLAHE(clipLimit=self.clip_limit, tileGridSize=self.tile_grid)
        return cv2.cvtColor(cv2.merge((clahe.apply(lightness), a, b)), cv2.COLOR_LAB2RGB)
