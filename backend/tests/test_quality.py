"""Tests para la parte 2: métricas y diagnóstico (album/quality.py)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from album.quality import diagnose, mse, psnr
from tests import synth

IMG = synth.photo()


def test_mse_identicas_es_cero():
    assert mse(IMG, IMG) == 0.0


def test_mse_valor_conocido():
    a = np.full((4, 4, 3), 100, dtype=np.uint8)
    b = np.full((4, 4, 3), 110, dtype=np.uint8)
    assert mse(a, b) == pytest.approx(100.0)


def test_psnr_identicas_es_infinito():
    assert math.isinf(psnr(IMG, IMG))


def test_psnr_crece_cuando_el_error_baja():
    noisier = synth.gaussian_noise(IMG, sigma=20, seed=7)
    closer = synth.gaussian_noise(IMG, sigma=5, seed=7)
    assert psnr(IMG, closer) > psnr(IMG, noisier)


def test_diagnostico_nitidez():
    sharp = diagnose(IMG)
    blurry = diagnose(synth.blurred(IMG))
    assert sharp.sharpness > blurry.sharpness * 10
    assert sharp.blurry is False
    assert blurry.blurry is True


def test_diagnostico_ruido():
    clean = diagnose(IMG)
    noisy = diagnose(synth.salt_pepper(IMG, amount=0.05))
    fine = diagnose(synth.gaussian_noise(IMG, sigma=15))
    assert clean.noisy is False
    assert noisy.noisy is True
    assert fine.noisy is True


def test_reporte_en_rangos_validos():
    report = diagnose(IMG)
    assert 0 <= report.mean_brightness <= 255
    assert report.sharpness >= 0
    assert report.noise >= 0
