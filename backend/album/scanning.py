"""TODO 1 (semana 1): digitalizar una foto impresa.

`Scanner.scan` recibe la foto de una foto impresa apoyada sobre una mesa y
devuelve la foto enderezada, como si se hubiera escaneado. Es el TP-2 rehecho
para el álbum (unidad 7.3 y ejercicio integrador 53), con la misma receta del
`ContourDetector` del TP-2:

  1. reducir la foto para trabajar rápido: lado mayor a 600 px (INTER_AREA) y
     guardar el factor de escala para devolver las esquinas a tamaño real;
  2. gris + desenfoque gaussiano 5×5 (tapa la textura de la mesa);
  3. Canny automático: umbrales (1 ± 0.33) × mediana del gris (ejercicio 25);
  4. cv2.morphologyEx MORPH_CLOSE con elipse 5×5: cierra los huecos que quedan
     entre los bordes de la hoja;
  5. cv2.findContours EXTERNAL, ordenar por área y probar los 5 contornos más
     grandes con cv2.approxPolyDP(epsilon = 2% del perímetro). Un contorno
     sirve si queda con 4 vértices convexos y ocupa al menos el 15% de la
     imagen reducida;
  6. ordenar las esquinas TL, TR, BR, BL (suma x+y mínima = TL, máxima = BR;
     diferencia y−x mínima = TR, máxima = BL) y deshacer la escala;
  7. si Canny no cierra el borde (mesa texturada, foto oscura), una segunda
     pasada segmenta con cv2.grabCut: el marco exterior se marca como fondo
     y el centro como objeto probable; el casco convexo del objeto más
     grande se aproxima a 4 vértices (con semilla fija: GrabCut ordena sus
     grupos al azar y así el mismo archivo da siempre lo mismo);
  8. enderezar con cv2.getPerspectiveTransform + cv2.warpPerspective al
     tamaño max(ancho_sup, ancho_inf) × max(alto_izq, alto_der), como el
     `PerspectiveCorrector` del TP-2.

Si ninguna pasada sirve, DocumentNotFound.

Convención: los puntos son (x, y) en píxeles, igual que usa OpenCV.
"""

from __future__ import annotations

import cv2
import numpy as np

from album.exceptions import DocumentNotFound

WORK_SIZE = 600        # lado mayor de la copia de trabajo
MIN_AREA_RATIO = 0.15  # la hoja tiene que ocupar al menos el 15% de la foto
BLUR_KERNEL = 5        # desenfoque gaussiano (impar)
CANNY_SIGMA = 0.33     # Canny automático: (1 ± σ) × mediana
MORPH_KERNEL = 5       # cierre de huecos en los bordes (unidad 2, 4)
APPROX_EPSILON = 0.02  # tolerancia de approxPolyDP: 2% del perímetro
MAX_CANDIDATES = 5     # contornos más grandes que se prueban
SEGMENT_WORK_SIZE = 400  # lado mayor de la copia para la segunda pasada
SEGMENT_INSET = 0.02     # margen del rectángulo inicial de GrabCut (fracción)
SEGMENT_ITERATIONS = 3   # pasadas de GrabCut
SEGMENT_SEED = 0         # semilla: GrabCut ordena sus grupos al azar
MIN_SIDE_RATIO = 0.02    # ningún lado del cuadrilátero mide menos que esto
SEGMENT_EPSILONS = (0.01, 0.02, 0.03, 0.05)  # tolerancias probadas en el casco


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
            quad = self._find_by_segmentation(small)
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
        pts = np.asarray(corners, dtype=np.float32)
        top_left, top_right, bottom_right, bottom_left = pts

        # Los lados opuestos de una hoja deberían medir parecido: nos quedamos
        # con el máximo de cada par para no perder contenido.
        width = round(max(
            np.linalg.norm(top_right - top_left),
            np.linalg.norm(bottom_right - bottom_left),
        ))
        height = round(max(
            np.linalg.norm(bottom_left - top_left),
            np.linalg.norm(bottom_right - top_right),
        ))

        destination = np.array([
            [0, 0],
            [width - 1, 0],
            [width - 1, height - 1],
            [0, height - 1],
        ], dtype=np.float32)

        transform = cv2.getPerspectiveTransform(pts, destination)
        return cv2.warpPerspective(image, transform, (width, height))

    def scan(self, image: np.ndarray) -> np.ndarray:
        """Detecta las esquinas y endereza. DocumentNotFound si no hay hoja."""
        return self.warp(image, self.detect_corners(image))

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

    def _find_by_segmentation(self, image: np.ndarray) -> np.ndarray | None:
        """Segunda pasada: separa la hoja de la mesa con GrabCut.

        Marca el marco exterior como fondo y el centro como objeto probable;
        la hoja es lo que queda. Después toma el casco convexo del objeto más
        grande y lo aproxima a 4 vértices probando tolerancias crecientes.
        Devuelve las esquinas en coordenadas de `image`.
        """
        height, width = image.shape[:2]
        scale = min(1.0, SEGMENT_WORK_SIZE / max(height, width))
        work = image
        if scale < 1.0:
            work = cv2.resize(
                image,
                (round(width * scale), round(height * scale)),
                interpolation=cv2.INTER_AREA,
            )
        work_height, work_width = work.shape[:2]
        inset_x = max(1, round(SEGMENT_INSET * work_width))
        inset_y = max(1, round(SEGMENT_INSET * work_height))
        rect = (inset_x, inset_y, work_width - 2 * inset_x, work_height - 2 * inset_y)
        if rect[2] < 8 or rect[3] < 8:
            return None

        mask = np.zeros((work_height, work_width), np.uint8)
        background = np.zeros((1, 65), np.float64)
        foreground = np.zeros((1, 65), np.float64)
        cv2.setRNGSeed(SEGMENT_SEED)
        cv2.grabCut(
            cv2.cvtColor(work, cv2.COLOR_RGB2BGR),
            mask,
            rect,
            background,
            foreground,
            SEGMENT_ITERATIONS,
            cv2.GC_INIT_WITH_RECT,
        )
        segmented = np.where(
            (mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0
        ).astype(np.uint8)
        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (self.morph_kernel, self.morph_kernel)
        )
        segmented = cv2.morphologyEx(segmented, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(segmented, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None
        hull = cv2.convexHull(max(contours, key=cv2.contourArea))
        min_area = self.min_area_ratio * work_height * work_width
        if cv2.contourArea(hull) < min_area:
            return None

        perimeter = cv2.arcLength(hull, True)
        for epsilon in SEGMENT_EPSILONS:
            polygon = cv2.approxPolyDP(hull, epsilon * perimeter, True)
            if len(polygon) != 4:
                continue
            # la aproximación puede juntar vértices: exigimos un cuadrilátero real
            if cv2.contourArea(polygon) < min_area:
                continue
            if not _has_four_sides(polygon.reshape(4, 2), MIN_SIDE_RATIO * perimeter):
                continue
            return polygon.reshape(4, 2).astype(np.float32) / scale
        return None


def _has_four_sides(points: np.ndarray, min_side: float) -> bool:
    """True si los 4 puntos son distintos y ningún lado es más corto que min_side."""
    sides = np.linalg.norm(np.roll(points, -1, axis=0) - points, axis=1)
    return bool(sides.min() >= min_side)


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
