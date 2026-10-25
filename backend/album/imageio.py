"""Entrada y salida de imágenes.

Convención del proyecto: una imagen es un array de NumPy
de forma (alto, ancho, 3), dtype uint8, en orden RGB. Se indexa [y, x]:
image[0, 0] es el píxel de arriba a la izquierda.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image

from album.exceptions import InvalidImage

MAX_SIDE = 4000  # las fotos más grandes que esto se reducen antes de procesar


@dataclass(frozen=True)
class ImageInfo:
    """La "ficha técnica" de una foto."""

    width: int
    height: int
    channels: int  # siempre 3: todo se abre como RGB
    dtype: str     # siempre "uint8"
    mode: str      # modo original de Pillow ("RGB", "L", "P", "CMYK", ...)


def decode(data: bytes) -> np.ndarray:
    """Bytes (PNG, JPEG, ...) → imagen RGB (alto, ancho, 3) uint8.

    Lanza InvalidImage si los bytes no se pueden abrir.
    """
    try:
        with Image.open(io.BytesIO(data)) as im:
            rgb = im.convert("RGB")
    except Exception:
        raise InvalidImage("No se pudo abrir la imagen (¿vacía, corrupta o no es una imagen?).") from None
    return np.asarray(rgb, dtype=np.uint8).copy()


def encode_png(image: np.ndarray) -> bytes:
    """Imagen RGB → bytes de un PNG."""
    buffer = io.BytesIO()
    _to_pil(image, "encode_png").save(buffer, format="PNG")
    return buffer.getvalue()


def inspect(data: bytes) -> ImageInfo:
    """Describe los bytes SIN procesarlos: tamaño, canales y modo original."""
    try:
        with Image.open(io.BytesIO(data)) as im:
            width, height = im.size
            mode = im.mode
    except Exception:
        raise InvalidImage("No se pudo abrir la imagen (¿vacía, corrupta o no es una imagen?).") from None
    return ImageInfo(width=width, height=height, channels=3, dtype="uint8", mode=mode)


def limit_side(image: np.ndarray, max_side: int = MAX_SIDE) -> np.ndarray:
    """Reduce la imagen si su lado más largo supera `max_side` (INTER_AREA)."""
    height, width = image.shape[:2]
    longest = max(height, width)
    if longest <= max_side:
        return image
    scale = max_side / longest
    size = (round(width * scale), round(height * scale))
    return cv2.resize(image, size, interpolation=cv2.INTER_AREA)


def to_pil(image: np.ndarray) -> Image.Image:
    """Array → imagen de Pillow (para mostrar o guardar)."""
    return _to_pil(image, "to_pil")


def _to_pil(image: np.ndarray, where: str) -> Image.Image:
    if not (isinstance(image, np.ndarray) and image.ndim == 3 and image.shape[2] == 3 and image.dtype == np.uint8):
        raise InvalidImage(f"{where}: se esperaba un array (alto, ancho, 3) uint8.")
    return Image.fromarray(image, "RGB")
