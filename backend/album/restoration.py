"""Parte 2: los pasos de restauración.

Cada paso es una clase con la interfaz `Step` (de album/pipeline.py): `apply`
recibe una imagen y devuelve una NUEVA, sin modificar la que recibe y sin
cambiar su tamaño. El pipeline los corre en este orden:

    foto dañada → DenoiseStep → ScratchRepairStep → ContrastStep

"""

from __future__ import annotations

from typing import Literal

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
SCRATCH_MIN_COMPONENT = 50          # píxeles: brillos de ojos y cejas son más chicos
SCRATCH_MIN_COMPONENT_FRACTION = 0.0001  # en fotos grandes, la textura ocupa más píxeles

CLAHE_CLIP_LIMIT = 2.5  # 2.0 (notebook) no llegaba a 1.3× en el sintético; 2.5 sí
CLAHE_TILE_GRID = (8, 8)


class DenoiseStep(Step):
    """Paso 1: quitar el ruido.

    Con method="auto" decide solo usando quality.diagnose:
      - (píxeles sueltos al 0 o al 255) → filtro de
        mediana (cv2.medianBlur, kernel impar chico, 3 o 5);
      - ruido fino gaussiano → filtro bilateral (preserva bordes mejor que
        el gaussiano: comparalo en el informe, es un experimento directo).
    Con "median" o "bilateral" no diagnostica: aplica ese filtro con los
    parámetros elegidos (ventana de la mediana; diámetro y sigma del bilateral).
    """

    number = 1
    name = "denoise"
    label = "Quitar ruido"

    def __init__(
        self,
        method: DenoiseMethod = "auto",
        kernel_size: int = MEDIAN_KERNEL,
        diameter: int = BILATERAL_DIAMETER,
        sigma: float = BILATERAL_SIGMA,
    ) -> None:
        self.method = method
        self.kernel_size = kernel_size
        self.diameter = diameter
        self.sigma = sigma

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(method={self.method!r}, kernel_size={self.kernel_size!r}, "
            f"diameter={self.diameter!r}, sigma={self.sigma!r})"
        )

    def apply(self, image: np.ndarray) -> np.ndarray:
        method = self.method
        if method == "auto":
            if not diagnose(image).noisy:
                return image.copy()  # no hay ruido que sacar
            method = "median" if _extreme_fraction(image) > SALT_PEPPER_FRACTION else "bilateral"

        if method == "median":
            return cv2.medianBlur(image, self.kernel_size)
        if method == "bilateral":
            return cv2.bilateralFilter(image, self.diameter, self.sigma, self.sigma)
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

    Todos esos valores se pueden ajustar desde la API: largo del kernel,
    contraste mínimo, radio de relleno y método (telea/ns).
    """

    number = 2
    name = "scratch_repair"
    label = "Reparar rasguños"

    def __init__(
        self,
        length: int = SCRATCH_LENGTH,
        min_contrast: int = SCRATCH_MIN_CONTRAST,
        radius: int = INPAINT_RADIUS,
        method: str = "telea",
    ) -> None:
        self.length = length
        self.min_contrast = min_contrast
        self.radius = radius
        self.method = method

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(length={self.length!r}, min_contrast={self.min_contrast!r}, "
            f"radius={self.radius!r}, method={self.method!r})"
        )

    def apply(self, image: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        horizontal = cv2.getStructuringElement(cv2.MORPH_RECT, (self.length, 1))
        vertical = cv2.getStructuringElement(cv2.MORPH_RECT, (1, self.length))

        # Una raya clara y fina no sobrevive a la apertura con un kernel
        # perpendicular a su dirección: queda en el top-hat.
        top_hat = cv2.max(
            cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, horizontal),
            cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, vertical),
        )

        threshold, _ = cv2.threshold(top_hat, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        if threshold < self.min_contrast:
            return image.copy()  # Otsu separó textura o grano, no rayas

        _, mask = cv2.threshold(top_hat, threshold, 255, cv2.THRESH_BINARY)
        mask = _drop_small_components(mask)
        if np.count_nonzero(mask) / mask.size > SCRATCH_MAX_FRACTION:
            return image.copy()  # demasiado "daño" para ser rasguños finos

        flags = cv2.INPAINT_TELEA if self.method == "telea" else cv2.INPAINT_NS
        return cv2.inpaint(image, mask, self.radius, flags)


def _drop_small_components(mask: np.ndarray) -> np.ndarray:
    """Deja solo los trazos largos: los brillos de ojos, cejas y el grano son chicos.

    El umbral Otsu solo no alcanza: en una cara también marca los reflejos de
    la mirada y, al rellenarlos, borra la expresión. Una raya tiene cientos de
    píxeles conectados; un reflejo, unas decenas.
    """
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
    min_area = max(SCRATCH_MIN_COMPONENT, round(mask.size * SCRATCH_MIN_COMPONENT_FRACTION))
    keep = np.zeros_like(mask)
    for label in range(1, count):
        if stats[label, cv2.CC_STAT_AREA] >= min_area:
            keep[labels == label] = 255
    return keep


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


WB_MIN_GAIN = 0.5              # límite de la corrección por canal (evita colores raros)
WB_MAX_GAIN = 2.0
WB_HIGHLIGHT_PERCENTILE = 99.5  # white patch: ignora los reflejos más extremos
STRETCH_LOW = 1.0              # percentiles del estiramiento del canal L
STRETCH_HIGH = 99.0


class WhiteBalanceStep(Step):
    """Paso 4: corregir la dominante de color y el contraste desvanecido.

    1. Balance de blancos (igual que en el TP-2):
       - "gray-world" supone que el promedio de la escena es gris: escala
         cada canal por media_gris / media_canal;
       - "white-patch" supone que el punto más claro es blanco: escala cada
         canal para llevar su percentil alto al 255.
    2. Estiramiento del histograma en LAB: lleva los percentiles 1 % y 99 %
       del canal L a 0 y 255 (sobre el gris, sin tocar el color).
    """

    number = 4
    name = "white_balance"
    label = "Balance de blancos"

    def __init__(
        self,
        method: Literal["gray-world", "white-patch"] = "gray-world",
        stretch: bool = True,
    ) -> None:
        self.method = method
        self.stretch = stretch

    def __repr__(self) -> str:
        return f"{type(self).__name__}(method={self.method!r}, stretch={self.stretch!r})"

    def apply(self, image: np.ndarray) -> np.ndarray:
        balanced = _balance_white(image, self.method)
        return _stretch_lightness(balanced) if self.stretch else balanced


def _balance_white(image: np.ndarray, method: str) -> np.ndarray:
    pixels = image.reshape(-1, 3).astype(np.float32)
    if method == "gray-world":
        means = pixels.mean(axis=0)
        gains = means.mean() / np.maximum(means, 1.0)
    else:
        highlights = np.percentile(pixels, WB_HIGHLIGHT_PERCENTILE, axis=0)
        gains = 255.0 / np.maximum(highlights, 1.0)
    gains = np.clip(gains, WB_MIN_GAIN, WB_MAX_GAIN)
    return np.clip(image.astype(np.float32) * gains, 0, 255).astype(np.uint8)


def _stretch_lightness(image: np.ndarray) -> np.ndarray:
    lightness, a, b = cv2.split(cv2.cvtColor(image, cv2.COLOR_RGB2LAB))
    low, high = np.percentile(lightness, (STRETCH_LOW, STRETCH_HIGH))
    if high <= low:
        return image.copy()  # no hay rango que estirar
    stretched = (lightness.astype(np.float32) - low) * (255.0 / (high - low))
    stretched = np.clip(stretched, 0, 255).astype(np.uint8)
    return cv2.cvtColor(cv2.merge((stretched, a, b)), cv2.COLOR_LAB2RGB)


SHARPEN_AMOUNT = 0.8  # cuánto se suma de la diferencia con la versión borrosa
SHARPEN_SIGMA = 1.2   # radio del desenfoque gaussiano (en píxeles)


class SharpenStep(Step):
    """Paso 5: realzar bordes con unsharp mask (receta del TP-2).

    Se desenfoca una copia con un gaussiano y se suma la diferencia:
        nítida = original + amount · (original − borrosa)
    Con amount bajo realza ojos, textura y bordes sin inflar el ruido;
    conviene aplicarlo siempre al final, después de quitar ruido.
    """

    number = 5
    name = "sharpen"
    label = "Realzar nitidez"

    def __init__(self, amount: float = SHARPEN_AMOUNT, sigma: float = SHARPEN_SIGMA) -> None:
        self.amount = amount
        self.sigma = sigma

    def __repr__(self) -> str:
        return f"{type(self).__name__}(amount={self.amount!r}, sigma={self.sigma!r})"

    def apply(self, image: np.ndarray) -> np.ndarray:
        if self.amount <= 0:
            return image.copy()
        blurred = cv2.GaussianBlur(image, (0, 0), self.sigma)
        return cv2.addWeighted(image, 1.0 + self.amount, blurred, -self.amount, 0)
