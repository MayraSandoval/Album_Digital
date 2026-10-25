"""Parte 1: digitalizar una foto impresa.

`Scanner.scan` recibe la foto de una foto impresa apoyada sobre una mesa y
devuelve la foto enderezada, como si se hubiera escaneado. 

"""

from __future__ import annotations

import cv2
import numpy as np

from album.exceptions import DocumentNotFound, NotImplementedYet

WORK_SIZE = 600        # lado mayor de la copia de trabajo
MIN_AREA_RATIO = 0.15  # la hoja tiene que ocupar al menos el 15% de la foto
BLUR_KERNEL = 5        # desenfoque gaussiano (impar)
CANNY_SIGMA = 0.33     # Canny automático: (1 ± ) × mediana
MORPH_KERNEL = 5       # cierre de huecos en los bordes (unidad 2, 4)
APPROX_EPSILON = 0.02  # tolerancia de approxPolyDP: 2% del perímetro
MAX_CANDIDATES = 5     # contornos más grandes que se prueban

class Scanner:
    """Digitaliza fotos impresas: detecta la hoja y endereza la perspectiva."""

    def __init__(
        self,
        work_size: int = WORK_SIZE,
        min_area_ratio: float = MIN_AREA_RATIO,
        blur_kernel: int = BLUR_KERNEL,
        canny_sigma: float = CANNY_SIGMA,
        morph_kernel: int = MORPH_KERNEL,
        approx_epsilon: float = APPROX_EPSILON,
        max_candidates: int = MAX_CANDIDATES,
    ) -> None:
        self.work_size = work_size
        self.min_area_ratio = min_area_ratio
        self.blur_kernel = blur_kernel
        self.canny_sigma = canny_sigma
        self.morph_kernel = morph_kernel
        self.approx_epsilon = approx_epsilon
        self.max_candidates = max_candidates

    def detect_corners(self, image: np.ndarray) -> np.ndarray:
        """Devuelve las 4 esquinas de la foto impresa.

        Array (4, 2) float32 o int, en el orden
        [arriba-izquierda, arriba-derecha, abajo-derecha, abajo-izquierda].

        Lanza DocumentNotFound si no encuentra un cuadrilátero dominante.
        """
        small, scale = self._resize(image)
        gray = self._preprocess(small)
        min_area = self.min_area_ratio * small.shape[0] * small.shape[1]

        quad = self._find_quadrilateral(self._edges(gray), min_area)
        if quad is None:
            raise DocumentNotFound(
                "No se encontró una hoja de cuatro esquinas que ocupe al menos "
                f"el {self.min_area_ratio:.0%} de la foto."
            )
        return _order_corners(quad / scale)

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



    def _resize(self, image: np.ndarray) -> tuple[np.ndarray, float]:
        """Copia reducida para trabajar rápido y el factor para deshacerla."""
        height, width = image.shape[:2]
        scale = min(1.0, self.work_size / max(height, width))
        if scale == 1.0:
            return image, scale
        size = (round(width * scale), round(height * scale))
        return cv2.resize(image, size, interpolation=cv2.INTER_AREA), scale

    def _preprocess(self, image: np.ndarray) -> np.ndarray:
        """Gris (RGB del álbum, no BGR) + desenfoque gaussiano."""
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        return cv2.GaussianBlur(gray, (self.blur_kernel, self.blur_kernel), 0)

    def _edges(self, gray: np.ndarray) -> np.ndarray:
        """Canny con umbrales automáticos + cierre morfológico de huecos."""
        median = float(np.median(gray))
        lower = int(max(0, (1 - self.canny_sigma) * median))
        upper = int(min(255, (1 + self.canny_sigma) * median))
        edges = cv2.Canny(gray, lower, upper)
        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (self.morph_kernel, self.morph_kernel)
        )
        return cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)

    def _find_quadrilateral(self, mask: np.ndarray, min_area: float) -> np.ndarray | None:
        """Prueba los contornos más grandes y devuelve el primero con 4 vértices."""
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        largest = sorted(contours, key=cv2.contourArea, reverse=True)[: self.max_candidates]
        for contour in largest:
            if cv2.contourArea(contour) < min_area:
                return None  # vienen de mayor a menor: los que siguen tampoco sirven
            perimeter = cv2.arcLength(contour, True)
            polygon = cv2.approxPolyDP(contour, self.approx_epsilon * perimeter, True)
            if len(polygon) == 4 and cv2.isContourConvex(polygon):
                return polygon.reshape(4, 2).astype(np.float32)
        return None


def _order_corners(points: np.ndarray) -> np.ndarray:
    """Ordena las esquinas como TL, TR, BR, BL (pista del ejercicio 53)."""
    pts = np.asarray(points, dtype=np.float32).reshape(4, 2)
    sums = pts.sum(axis=1)                # x + y de cada punto
    diffs = np.diff(pts, axis=1).ravel()  # y - x de cada punto

    return np.array([
        pts[np.argmin(sums)],   # arriba-izquierda: suma mínima
        pts[np.argmin(diffs)],  # arriba-derecha: y - x mínima
        pts[np.argmax(sums)],   # abajo-derecha: suma máxima
        pts[np.argmax(diffs)],  # abajo-izquierda: y - x máxima
    ], dtype=np.float32)
