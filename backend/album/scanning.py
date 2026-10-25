"""Parte 1: digitalizar una foto impresa.

`Scanner.scan` recibe la foto de una foto impresa apoyada sobre una mesa y
devuelve la foto enderezada, como si se hubiera escaneado. 

"""

from __future__ import annotations

import numpy as np

from album.exceptions import DocumentNotFound, NotImplementedYet


class Scanner:
    """Digitaliza fotos impresas: detecta la hoja y endereza la perspectiva."""

    def detect_corners(self, image: np.ndarray) -> np.ndarray:
        """Devuelve las 4 esquinas de la foto impresa.

        Array (4, 2) float32 o int, en el orden
        [arriba-izquierda, arriba-derecha, abajo-derecha, abajo-izquierda].

        Lanza DocumentNotFound si no encuentra un cuadrilátero dominante.
        """
        raise NotImplementedYet("Scanner.detect_corners (album/scanning.py)")

    def warp(self, image: np.ndarray, corners: np.ndarray) -> np.ndarray:
        """Endereza la foto: la esquina TL de `corners` pasa a ser (0, 0).

        Devuelve una imagen RGB (alto, ancho, 3) uint8 de tamaño
        max(ancho_sup, ancho_inf) × max(alto_izq, alto_der) — sin recortar
        contenido por quedar corta de píxeles.
        """
        raise NotImplementedYet("Scanner.warp (album/scanning.py)")

    def scan(self, image: np.ndarray) -> np.ndarray:
        """Detecta las esquinas y endereza. DocumentNotFound si no hay hoja."""
        raise NotImplementedYet("Scanner.scan (album/scanning.py)")
