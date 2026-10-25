"""Tests para la parte 1: Scanner (album/scanning.py)."""

from __future__ import annotations

import numpy as np
import pytest

from album.exceptions import DocumentNotFound
from album.scanning import Scanner
from tests import synth


@pytest.fixture(scope="module")
def scanner():
    return Scanner()


@pytest.fixture(scope="module")
def paper():
    return synth.paper_on_table()


def test_detecta_cuatro_esquinas_en_orden(scanner, paper):
    image, truth = paper
    corners = scanner.detect_corners(image)
    assert isinstance(corners, np.ndarray) and corners.shape == (4, 2)
    assert np.allclose(corners, truth, atol=5), f"esperaba {truth.tolist()}, obtuve {np.asarray(corners).tolist()}"


def test_warp_devuelve_imagen_valida(scanner, paper):
    image, truth = paper
    warped = scanner.warp(image, truth)
    assert isinstance(warped, np.ndarray) and warped.ndim == 3 and warped.shape[2] == 3
    assert warped.dtype == np.uint8


def test_warp_sin_recortar_contenido(scanner, paper):
    """El tamaño sale de los lados del cuadrilátero (máximos), no de un fijo."""
    image, truth = paper
    warped = scanner.warp(image, truth)
    height, width = warped.shape[:2]
    assert 150 <= height <= 230, f"alto inesperado: {height}"
    assert 240 <= width <= 320, f"ancho inesperado: {width}"


def test_warp_endereza_la_hoja(scanner, paper):
    """Después de enderezar, el papel claro ocupa casi todo el cuadro."""
    image, truth = paper
    warped = scanner.warp(image, truth)
    gray = warped.mean(axis=2)
    assert gray.mean() > 180, f"la foto enderezada quedó oscura (media {gray.mean():.1f})"


def test_scan_devuelve_la_foto_enderezada(scanner, paper):
    image, _ = paper
    result = scanner.scan(image)
    assert result.shape[0] > 100 and result.shape[1] > 100
    assert result.mean(axis=2).mean() > 180


def test_scan_sin_hoja_lanza_document_not_found(scanner):
    with pytest.raises(DocumentNotFound):
        scanner.scan(synth.plain())
