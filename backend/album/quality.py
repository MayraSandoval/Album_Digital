"""Parte 2: métricas de calidad y diagnóstico de una foto.

Dos usos dentro del álbum:
  - `mse` y `psnr` miden cuánto se parece una restauración al original sin
    daño. Son las métricas de los experimentos comparativos: mediana contra bilateral, inpainting TELEA contra NS.
  - `diagnose` es el "triage" de la restauración: dice qué tan
    borrosa y qué tan ruidosa está la foto para decidir cómo tratarla.

"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

BLURRY_SHARPNESS = 100.0  # por debajo de esto la foto se considera borrosa
NOISY_STD = 10.0          # por encima de esto la foto se considera ruidosa
MEDIAN_KERNEL = 5         # ventana impar para estimar el ruido


def mse(a: np.ndarray, b: np.ndarray) -> float:
    """Error cuadrático medio entre dos imágenes del mismo tamaño.

    Imágenes idénticas → 0.0.
    """
    if a.shape != b.shape:
        raise ValueError(f"Las imágenes deben tener el mismo tamaño: {a.shape} contra {b.shape}.")

    # Cast a float64 indispensable: en uint8, 10 - 20 da 246 (módulo 256).
    diff = a.astype(np.float64) - b.astype(np.float64)
    return float(np.mean(diff ** 2))


def psnr(a: np.ndarray, b: np.ndarray, max_val: float = 255.0) -> float:
    """Peak Signal-to-Noise Ratio en decibeles (más alto = más parecidas).

    Imágenes idénticas → float("inf").
    """
    error = mse(a, b)
    if error == 0.0:
        return float("inf")
    return float(20.0 * np.log10(max_val / np.sqrt(error)))


@dataclass(frozen=True)
class QualityReport:
    """El diagnóstico de una foto."""

    sharpness: float        # varianza del Laplaciano (más alto = más nítida)
    noise: float            # desvío estándar estimado del ruido (0..255)
    mean_brightness: float  # brillo promedio del gris (0..255)
    blurry: bool            # sharpness por debajo del umbral elegido
    noisy: bool             # noise por encima del umbral elegido


def diagnose(image: np.ndarray) -> QualityReport:
    """Analiza la foto y decide si está borrosa y/o ruidosa."""
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

    # Nitidez: los bordes nítidos dan un Laplaciano con mucha varianza;
    # el desenfoque los aplana y la varianza cae.
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    # Ruido fino: la mediana lo elimina, así que sobrevive en la diferencia.
    smooth = cv2.medianBlur(gray, MEDIAN_KERNEL)
    noise = float(np.std(gray.astype(np.float64) - smooth.astype(np.float64)))

    return QualityReport(
        sharpness=sharpness,
        noise=noise,
        mean_brightness=float(gray.mean()),
        blurry=sharpness < BLURRY_SHARPNESS,
        noisy=noise > NOISY_STD,
    )
