"""Imágenes sintéticas para los tests.

Todo es determinista (semillas fijas): los mismos tests dan los mismos
números siempre. También sirven de ejemplo de cómo fabricar daños para los
experimentos del informe.
"""

from __future__ import annotations

import cv2
import numpy as np


def photo(width: int = 240, height: int = 180, seed: int = 0) -> np.ndarray:
    """Una "foto" con gradiente, formas y grano: nítida, limpia y colorida."""
    rng = np.random.default_rng(seed)
    x = np.linspace(0, 255, width, dtype=np.float32)
    base = np.tile(x, (height, 1))
    image = np.stack([base, 255 - base, base * 0.5 + 40], axis=-1)
    image = np.clip(image, 0, 255).astype(np.uint8)
    cv2.circle(image, (width // 3, height // 2), height // 4, (250, 60, 60), -1)
    cv2.rectangle(image, (width // 2, 20), (width - 20, height - 20), (40, 200, 90), 3)
    grain = rng.normal(0, 4, image.shape)
    return np.clip(image.astype(np.float32) + grain, 0, 255).astype(np.uint8)


def solid(width: int = 200, height: int = 160, rgb: tuple[int, int, int] = (200, 30, 30)) -> np.ndarray:
    """Una imagen de un solo color (para búsqueda por color)."""
    return np.full((height, width, 3), rgb, dtype=np.uint8)


def paper_on_table(width: int = 320, height: int = 240) -> tuple[np.ndarray, np.ndarray]:
    """Una "foto impresa" clara apoyada sobre una mesa oscura.

    Devuelve (imagen, esquinas_reales) con las esquinas en el orden
    [TL, TR, BR, BL] y formato (x, y) — la verdad contra la que se compara
    Scanner.detect_corners.
    """
    x = np.linspace(30, 80, width, dtype=np.float32)
    table = np.tile(x, (height, 1))
    image = np.stack([table, table * 0.9, table * 0.7], axis=-1)
    image = np.clip(image, 0, 255).astype(np.uint8)
    corners = np.array([[40, 30], [280, 20], [300, 205], [25, 215]], dtype=np.int32)
    cv2.fillConvexPoly(image, corners, (245, 242, 235))
    cv2.circle(image, (width // 2, height // 2), 36, (60, 60, 80), -1)
    cv2.rectangle(image, (width // 2 - 70, height // 2 - 50), (width // 2 + 70, height // 2 + 50), (120, 90, 60), 2)
    return image, corners.astype(np.float32)


def plain(width: int = 320, height: int = 240) -> np.ndarray:
    """Un fondo sin ninguna hoja: el Scanner debe decir DocumentNotFound."""
    x = np.linspace(0, 200, width, dtype=np.float32)
    image = np.tile(x, (height, 1))
    return np.stack([image, image * 0.8, image * 0.6], axis=-1).astype(np.uint8)


def salt_pepper(image: np.ndarray, amount: float = 0.05, seed: int = 1) -> np.ndarray:
    """Ruido de sal y pimienta: `amount` fracción de píxeles al 0 o al 255."""
    rng = np.random.default_rng(seed)
    out = image.copy()
    n = round(image.shape[0] * image.shape[1] * amount)
    for _ in range(n):
        y, x = rng.integers(0, image.shape[0]), rng.integers(0, image.shape[1])
        out[y, x] = 255 if rng.random() < 0.5 else 0
    return out


def gaussian_noise(image: np.ndarray, sigma: float = 15.0, seed: int = 2) -> np.ndarray:
    """Ruido fino gaussiano en cada canal."""
    rng = np.random.default_rng(seed)
    noise = rng.normal(0, sigma, image.shape)
    return np.clip(image.astype(np.float32) + noise, 0, 255).astype(np.uint8)


def scratched(image: np.ndarray) -> np.ndarray:
    """Dos rasguños claros: una raya horizontal gruesa y una vertical fina."""
    out = image.copy()
    h, w = out.shape[:2]
    out[h // 2 - 1 : h // 2 + 1, :, :] = 255  # horizontal, 2 px de alto
    out[:, w // 3, :] = 255                   # vertical, 1 px de ancho
    return out


def blurred(image: np.ndarray, kernel: int = 9) -> np.ndarray:
    return cv2.GaussianBlur(image, (kernel, kernel), 0)


def low_contrast(image: np.ndarray) -> np.ndarray:
    """Comprime el rango de tonos: casi negra contra casi negra."""
    return np.clip(image.astype(np.float32) * 0.25 + 80, 0, 255).astype(np.uint8)
