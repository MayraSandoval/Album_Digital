"""Test para la Parte 4: descriptores (album/descriptors.py)."""

from __future__ import annotations

import numpy as np
import pytest

from album import descriptors
from tests import synth

IMG = synth.photo()
OTHER = 255 - synth.photo()  # invertida: misma estructura, colores opuestos


def test_hash_de_la_misma_foto_es_igual():
    assert descriptors.hamming(descriptors.perceptual_hash(IMG), descriptors.perceptual_hash(IMG.copy())) == 0


def test_hash_tolera_cambios_chicos():
    """Una versión un poco más clara debe seguir siendo "la misma" foto."""
    brighter = np.clip(IMG.astype(np.int32) + 25, 0, 255).astype(np.uint8)
    assert descriptors.hamming(descriptors.perceptual_hash(IMG), descriptors.perceptual_hash(brighter)) <= 12


def test_hash_distingue_fotos_distintas():
    assert descriptors.hamming(descriptors.perceptual_hash(IMG), descriptors.perceptual_hash(OTHER)) >= 20


def test_hamming_cuenta_bits():
    a = 0xF0F0F0F0F0F0F0F0
    b = 0x0F0F0F0F0F0F0F0F
    assert descriptors.hamming(a, b) == 64
    assert descriptors.hamming(a, a) == 0
    assert descriptors.hamming(0, 1) == 1


def test_histograma_normalizado():
    hist = descriptors.color_histogram(IMG, bins=8)
    assert isinstance(hist, np.ndarray) and hist.shape == (24,)
    assert (hist >= 0).all()
    assert hist.sum() == np.float64(1.0) or abs(hist.sum() - 1.0) < 1e-6


def test_distancia_de_histogramas():
    hist_a = descriptors.color_histogram(IMG)
    assert descriptors.histogram_distance(hist_a, hist_a) == pytest.approx(0.0, abs=1e-9)
    inverted = 255 - IMG
    assert descriptors.histogram_distance(hist_a, descriptors.color_histogram(inverted)) > 1.0


def test_color_fraction_acierta_el_color():
    red = synth.solid(rgb=(180, 25, 25))
    assert descriptors.color_fraction(red, (180, 25, 25)) > 0.9


def test_color_fraction_rechaza_otro_color():
    red = synth.solid(rgb=(180, 25, 25))
    assert descriptors.color_fraction(red, (25, 25, 180)) < 0.1


def test_color_fraction_ignora_los_grises():
    gray = synth.solid(rgb=(120, 120, 120))
    assert descriptors.color_fraction(gray, (120, 120, 120)) < 0.1


def test_color_fraction_con_rojo_partido():
    """El rojo vive en los dos extremos de H: la máscara debe unirlos."""
    red = synth.solid(rgb=(200, 30, 30))
    assert descriptors.color_fraction(red, (255, 0, 0)) > 0.9
