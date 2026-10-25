"""Parte 3: descriptores para organizar y buscar en el álbum.

Con estas piezas la app detecta duplicados al subir una foto y busca por
color o por similitud.

"""

from __future__ import annotations

import numpy as np

from album.exceptions import NotImplementedYet


def perceptual_hash(image: np.ndarray) -> int:
    """Hash perceptual de 64 bits: fotos parecidas dan hashes parecidos."""
    raise NotImplementedYet("descriptors.perceptual_hash (album/descriptors.py)")


def hamming(a: int, b: int) -> int:
    """Cantidad de bits distintos entre dos hashes de 64 bits (0..64)."""
    raise NotImplementedYet("descriptors.hamming (album/descriptors.py)")


def color_histogram(image: np.ndarray, bins: int = 8) -> np.ndarray:
    """Histograma de color concatenado y normalizado (longitud 3·bins)."""
    raise NotImplementedYet("descriptors.color_histogram (album/descriptors.py)")


def histogram_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Distancia L1 entre dos histogramas normalizados (0.0 = idénticos)."""
    raise NotImplementedYet("descriptors.histogram_distance (album/descriptors.py)")


def color_fraction(image: np.ndarray, rgb: tuple[int, int, int], tolerance: int = 12) -> float:
    """Fracción de píxeles (0..1) del color `rgb` (RGB 0-255) con radio `tolerance` en H."""
    raise NotImplementedYet("descriptors.color_fraction (album/descriptors.py)")
