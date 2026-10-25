"""Parte 2: métricas de calidad y diagnóstico de una foto.

Dos usos dentro del álbum:
  - `mse` y `psnr` miden cuánto se parece una restauración al original sin
    daño. Son las métricas de los experimentos comparativos
    del informe: mediana contra bilateral, inpainting TELEA contra NS.
  - `diagnose` es el "triage" de la restauración: dice qué tan
    borrosa y qué tan ruidosa está la foto para decidir cómo tratarla.

"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from album.exceptions import NotImplementedYet


def mse(a: np.ndarray, b: np.ndarray) -> float:
    """Error cuadrático medio entre dos imágenes del mismo tamaño.

    Imágenes idénticas → 0.0.
    """
    raise NotImplementedYet("quality.mse (album/quality.py)")


def psnr(a: np.ndarray, b: np.ndarray) -> float:
    """Peak Signal-to-Noise Ratio en decibeles (más alto = más parecidas).

    Imágenes idénticas → float("inf").
    """
    raise NotImplementedYet("quality.psnr (album/quality.py)")


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
    raise NotImplementedYet("quality.diagnose (album/quality.py)")
