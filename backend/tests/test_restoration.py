"""Tests para la parte 3: los pasos de restauración (album/restoration.py).

Los primeros tests prueban la mecánica del pipeline. Los
últimos prueban el EFECTO de cada paso.
"""

from __future__ import annotations

import numpy as np

from album import RestorationOptions, RestorationPipeline, Step
from album.exceptions import NotImplementedYet
from album.quality import diagnose
from album.restoration import (
    ContrastStep,
    DenoiseStep,
    ScratchRepairStep,
    SharpenStep,
    WhiteBalanceStep,
)
from tests import synth

IMG = synth.photo()
PIPELINE = RestorationPipeline()


# ------------------------------------------------------- mecánica


def test_pasos_pendientes_se_saltean():
    class Pending(Step):
        name = "pending"
        label = "Pendiente"

        def apply(self, image):
            raise NotImplementedYet("todavía no")

    trace = PIPELINE.run(IMG, steps=[Pending()])
    assert [r.status for r in trace.results] == ["pending"]
    assert np.array_equal(trace.image, IMG)
    assert trace.complete is False


def test_las_opciones_quitan_pasos():
    options = RestorationOptions(denoise="none", repair_scratches=False, contrast=False)
    trace = PIPELINE.run(IMG, options)
    assert trace.results == []


def test_paso_fallido_bloquea_los_siguientes():
    class Broken(Step):
        name = "broken"
        label = "Roto"

        def apply(self, image):
            raise ValueError("boom")

    class Ok(Step):
        name = "ok"
        label = "Anda"

        def apply(self, image):
            return image.copy()

    trace = PIPELINE.run(IMG, steps=[Broken(), Ok()])
    assert [r.status for r in trace.results] == ["failed", "blocked"]
    assert trace.failure is not None and "boom" in trace.failure.message


def test_paso_que_cambia_el_tamano_falla():
    class Resizer(Step):
        name = "resizer"
        label = "Cambia tamaño"

        def apply(self, image):
            return np.zeros((4, 4, 3), dtype=np.uint8)

    trace = PIPELINE.run(IMG, steps=[Resizer()])
    assert trace.results[0].status == "failed"
    assert "tamaño" in trace.results[0].message


# ------------------------------------------------- efecto de cada paso


def test_denoise_quita_sal_y_pimienta():
    damaged = synth.salt_pepper(IMG, amount=0.05)
    before = _extreme_pixels(damaged)
    assert before > 1000  # hay daño medible
    restored = DenoiseStep(method="median").apply(damaged)
    assert _extreme_pixels(restored) < before // 10


def _extreme_pixels(image: np.ndarray) -> int:
    """Píxeles casi negros o casi blancos en los TRES canales (sal y pimienta)."""
    dark = (image <= 10).all(axis=2)
    bright = (image >= 245).all(axis=2)
    return int((dark | bright).sum())


def test_scratch_repair_tapa_las_rayas():
    damaged = synth.scratched(IMG)
    row = damaged.shape[0] // 2
    before = damaged[row - 1 : row + 1, :, :].mean()
    restored = ScratchRepairStep().apply(damaged)
    after = restored[row - 1 : row + 1, :, :].mean()
    assert after < before - 50, f"la raya sigue clara: {before:.0f} → {after:.0f}"


def test_contrast_step_amplia_el_rango():
    flat = synth.low_contrast(IMG)
    before = flat.mean(axis=2).std()
    restored = ContrastStep().apply(flat)
    after = restored.mean(axis=2).std()
    assert after > before * 1.3, f"el contraste no subió: {before:.1f} → {after:.1f}"


def test_denoise_mediana_respeta_la_ventana():
    damaged = synth.salt_pepper(IMG, amount=0.05)
    small = DenoiseStep(method="median", kernel_size=3).apply(damaged)
    big = DenoiseStep(method="median", kernel_size=9).apply(damaged)
    assert not np.array_equal(small, big)


def test_scratch_respeta_el_metodo_de_relleno():
    damaged = synth.scratched(IMG)
    telea = ScratchRepairStep(method="telea").apply(damaged)
    ns = ScratchRepairStep(method="ns").apply(damaged)
    assert not np.array_equal(telea, ns)


def test_contraste_respeta_el_clip():
    flat = synth.low_contrast(IMG)
    soft = ContrastStep(clip_limit=1.0).apply(flat)
    strong = ContrastStep(clip_limit=6.0).apply(flat)
    assert not np.array_equal(soft, strong)


def test_white_balance_neutraliza_una_dominante():
    casted = np.clip(IMG.astype(np.float32) * np.array([1.2, 1.0, 0.8]), 0, 255).astype(np.uint8)
    balanced = WhiteBalanceStep(method="gray-world", stretch=False).apply(casted)
    means = balanced.reshape(-1, 3).mean(axis=0)
    assert means.max() - means.min() < 5, f"quedó dominante: {means}"


def test_white_patch_lleva_los_blancos_al_maximo():
    casted = np.clip(IMG.astype(np.float32) * np.array([1.2, 1.0, 0.8]), 0, 255).astype(np.uint8)
    balanced = WhiteBalanceStep(method="white-patch", stretch=False).apply(casted)
    highlights = np.percentile(balanced.reshape(-1, 3), 99.5, axis=0)
    assert np.all(highlights > 245), f"los blancos no llegaron al máximo: {highlights}"


def test_estirar_el_histograma_amplia_el_rango():
    flat = synth.low_contrast(IMG)
    before = flat.mean(axis=2).std()
    stretched = WhiteBalanceStep(method="gray-world", stretch=True).apply(flat)
    after = stretched.mean(axis=2).std()
    assert after > before * 1.3, f"el rango no se amplió: {before:.1f} → {after:.1f}"


def test_sharpen_aumenta_la_nitidez():
    soft = synth.blurred(IMG, kernel=5)
    before = diagnose(soft).sharpness
    sharp = SharpenStep(amount=1.2, sigma=1.5).apply(soft)
    after = diagnose(sharp).sharpness
    assert after > before * 2, f"la nitidez no subió: {before:.0f} → {after:.0f}"


def test_sharpen_con_amount_cero_no_cambia_nada():
    assert np.array_equal(SharpenStep(amount=0).apply(IMG), IMG)


def test_los_pasos_no_modifican_la_entrada():
    steps = (DenoiseStep("median"), ScratchRepairStep(), ContrastStep(), WhiteBalanceStep(), SharpenStep())
    for step in steps:
        damaged = synth.salt_pepper(synth.scratched(IMG))
        original = damaged.copy()
        try:
            step.apply(damaged)
        except NotImplementedYet:
            continue  # todavía no está: nada que verificar
        assert np.array_equal(damaged, original), f"{type(step).__name__} modificó la imagen de entrada"


def test_pipeline_completo_restaura():
    damaged = synth.salt_pepper(synth.scratched(IMG))
    trace = PIPELINE.run(damaged)
    assert trace.complete is True, f"estados: {[(r.status, r.message) for r in trace.results]}"
    assert not np.array_equal(trace.image, damaged)
