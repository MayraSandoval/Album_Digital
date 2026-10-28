"""TODO 4 (semana 3): descriptores para organizar y buscar en el álbum.

Con estas piezas la app detecta duplicados al subir una foto y busca por
color o por similitud (unidad 7.3 y ejercicios 30, 54 y 55).

Pistas:
  - perceptual_hash (ejercicio 55): gris → cv2.resize a 8×8 → promedio →
    64 bits, uno por píxel: 1 si el píxel ≥ promedio. Devolvé un int.
  - hamming: cantidad de bits distintos entre dos hashes (bin(a ^ b) cuenta
    los unos).
  - color_histogram (ejercicio 30): histograma de los 3 canales con `bins`
    cubetas por canal, concatenado (longitud 3·bins) y normalizado para que
    la suma sea 1.
  - histogram_distance: distancia L1 entre dos histogramas normalizados
    (0.0 = idénticos, 2.0 = opuestos): sum(|a − b|).
  - color_fraction (ejercicio 54): fracción de píxeles del color objetivo.
    Trabajá en HSV con cv2.COLOR_RGB2HSV: un píxel cuenta si su canal H está
    a menos de `tolerance` del H del objetivo Y además S > 40 y V > 40 (para
    ignorar los grises, que tienen H sin sentido). Atención: el rojo está
    partido en los dos extremos del rango de H (0-179): para un objetivo
    rojo vas a necesitar dos máscaras unidas con cv2.bitwise_or.
"""

from __future__ import annotations

import cv2
import numpy as np

HASH_SIDE = 8              # 8×8 = 64 bits, como el aHash del ejercicio 55
MIN_SATURATION = 40        # por debajo de esto el píxel es gris: su H no significa nada
MIN_VALUE = 40             # descarta negros y sombras donde el color no se distingue
HUE_WRAP = 180             # el canal H de OpenCV en uint8 va de 0 a 179


def perceptual_hash(image: np.ndarray) -> int:
    """Hash perceptual de 64 bits: fotos parecidas dan hashes parecidos.

    Es el aHash del ejercicio 55: gris, resize a 8×8 con INTER_AREA y un bit
    por píxel (1 si está en el promedio o arriba). El orden de lectura es el
    de `ravel`: fila por fila, de arriba a la izquierda a abajo a la derecha.
    """
    gris = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    pequena = cv2.resize(gris, (HASH_SIDE, HASH_SIDE), interpolation=cv2.INTER_AREA)
    bits = pequena.ravel() >= pequena.mean()

    value = 0
    for bit in bits:
        value = (value << 1) | int(bit)
    return value


def hamming(a: int, b: int) -> int:
    """Cantidad de bits distintos entre dos hashes de 64 bits (0..64)."""
    return bin(a ^ b).count("1")


def color_histogram(image: np.ndarray, bins: int = 8) -> np.ndarray:
    """Histograma de color concatenado y normalizado (longitud 3·bins).

    Un histograma por canal de HSV con cv2.calcHist (ejercicio 30): separa el
    color (H y S) del brillo (V), así que dos fotos de la misma escena con
    distinta luz quedan cerca. Los tres histogramas se concatenan y se
    normalizan en L1 para que la suma total sea 1 y el tamaño de la foto no
    contamine la comparación. La imagen llega en RGB.
    """
    hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
    ranges = ((0, 180), (0, 256), (0, 256))
    parts = []
    for channel, (low, high) in enumerate(ranges):
        hist = cv2.calcHist([hsv], [channel], None, [bins], [low, high])
        parts.append(hist.ravel())
    return cv2.normalize(np.concatenate(parts), None, alpha=1.0, norm_type=cv2.NORM_L1)


def histogram_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Distancia L1 entre dos histogramas normalizados (0.0 = idénticos)."""
    return float(np.abs(a - b).sum())


def color_fraction(image: np.ndarray, rgb: tuple[int, int, int], tolerance: int = 12) -> float:
    """Fracción de píxeles (0..1) del color `rgb` (RGB 0-255) con radio `tolerance` en H."""
    hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
    target_h = int(cv2.cvtColor(np.array([[rgb]], dtype=np.uint8), cv2.COLOR_RGB2HSV)[0, 0, 0])

    def mask_between(h_low: int, h_high: int) -> np.ndarray:
        lower = np.array([h_low, MIN_SATURATION, MIN_VALUE], dtype=np.uint8)
        upper = np.array([h_high, 255, 255], dtype=np.uint8)
        return cv2.inRange(hsv, lower, upper)

    low = target_h - tolerance
    high = target_h + tolerance
    if low < 0:
        # El rojo cruza el 0: una banda [0, high] y otra [180 + low, 179].
        mask = cv2.bitwise_or(mask_between(0, high), mask_between(HUE_WRAP + low, HUE_WRAP - 1))
    elif high >= HUE_WRAP:
        mask = cv2.bitwise_or(mask_between(low, HUE_WRAP - 1), mask_between(0, high - HUE_WRAP))
    else:
        mask = mask_between(low, high)

    return float(np.count_nonzero(mask) / mask.size)
