"""Parte 2: los pasos de restauración.

Cada paso es una clase con la interfaz `Step` (de album/pipeline.py): `apply`
recibe una imagen y devuelve una NUEVA, sin modificar la que recibe y sin
cambiar su tamaño. El pipeline los corre en este orden:

    foto dañada → DenoiseStep → ScratchRepairStep → ContrastStep

"""

from __future__ import annotations

import numpy as np

from album.exceptions import NotImplementedYet
from album.pipeline import DenoiseMethod, Step


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
        raise NotImplementedYet("DenoiseStep.apply (album/restoration.py)")


class ScratchRepairStep(Step):
    """Paso 2: tapar rasguños.

      1. detectá las rayas claras y finas con un top-hat blanco
         (cv2.morphologyEx con MORPH_TOPHAT) y un kernel alargado
         (cv2.getStructuringElement con forma RECT de, p. ej., 25×1 para
         rayas horizontales; probá también 1×25 para verticales);
      2. umbralizá el top-hat para quedarte con una máscara de los daños
         (cv2.threshold con un valor alto, o directamente Otsu);
      3. rellená con cv2.inpaint usando Inpainting TELEA o NS (comparalos:
         es otro experimento para el informe).
    """

    number = 2
    name = "scratch_repair"
    label = "Reparar rasguños"

    def apply(self, image: np.ndarray) -> np.ndarray:
        raise NotImplementedYet("ScratchRepairStep.apply (album/restoration.py)")


class ContrastStep(Step):
    """Paso 3: realce de contraste local.

    CLAHE sobre el canal de luminancia (pasá a LAB con
    cv2.COLOR_RGB2LAB, realzá el canal L con cv2.createCLAHE y volvé a RGB)
    para aclarar sombras sin quemar las luces. Elegí clipLimit y tileGridSize
    probando con fotos reales y justificálos en el informe.
    """

    number = 3
    name = "contrast"
    label = "Realzar contraste"

    def apply(self, image: np.ndarray) -> np.ndarray:
        raise NotImplementedYet("ContrastStep.apply (album/restoration.py)")
