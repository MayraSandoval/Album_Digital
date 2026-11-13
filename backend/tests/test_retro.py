"""Tests del estilo retro: paletas, cuantización y dithering."""

from __future__ import annotations

import numpy as np
import pytest

from album.retro import (
    PALETTES,
    RetroOptions,
    UnknownPalette,
    apply_retro,
    floyd_steinberg,
    gradient_map,
    nearest_color,
    palette_map,
)
from tests import synth

IMG = synth.photo()


def _colors(image: np.ndarray) -> set[tuple[int, int, int]]:
    return {tuple(color) for color in image.reshape(-1, 3).tolist()}


def _palette_colors(name: str) -> set[tuple[int, int, int]]:
    return {tuple(color) for color in PALETTES[name].colors.tolist()}


def test_paletas_del_tp3():
    assert set(PALETTES) == {"gameboy", "bw", "virtualboy", "cga", "pico8"}
    assert PALETTES["gameboy"].colors.tolist() == [
        [15, 56, 15],
        [48, 98, 48],
        [139, 172, 15],
        [155, 188, 15],
    ]
    assert PALETTES["gameboy"].monochrome is True
    assert PALETTES["cga"].monochrome is False
    assert len(PALETTES["pico8"].hex_colors) == 16


def test_nearest_color_y_empate_gana_el_primero():
    colors = np.array([[0, 0, 0], [10, 0, 0]], dtype=np.uint8)
    assert nearest_color(np.array([2, 0, 0]), colors).tolist() == [0, 0, 0]
    assert nearest_color(np.array([8, 0, 0]), colors).tolist() == [10, 0, 0]
    assert nearest_color(np.array([5, 0, 0]), colors).tolist() == [0, 0, 0]


def test_gradient_map_usa_la_rampa_de_la_paleta():
    mapped = gradient_map(IMG, PALETTES["gameboy"])
    assert mapped.shape == IMG.shape and mapped.dtype == np.uint8
    assert len(_colors(mapped)) > len(PALETTES["gameboy"].hex_colors)
    assert mapped[..., 1].mean() > mapped[..., 0].mean()
    assert mapped[..., 1].mean() > mapped[..., 2].mean()


def test_gradient_map_no_falla_con_imagen_plana():
    mapped = gradient_map(synth.solid(rgb=(128, 128, 128)), PALETTES["bw"])
    assert len(_colors(mapped)) == 1
    assert 120 <= mapped[0, 0, 0] <= 136


def test_palette_map_solo_usa_colores_de_la_paleta():
    mapped = palette_map(IMG, PALETTES["cga"])
    assert _colors(mapped) <= _palette_colors("cga")
    assert mapped.shape == IMG.shape and mapped.dtype == np.uint8


@pytest.mark.parametrize("name", list(PALETTES))
def test_floyd_steinberg_solo_usa_colores_de_la_paleta(name):
    mapped = floyd_steinberg(IMG, PALETTES[name])
    assert _colors(mapped) <= _palette_colors(name)
    assert mapped.shape == IMG.shape and mapped.dtype == np.uint8


def test_dithering_cambia_el_resultado():
    sin_dither = apply_retro(IMG, RetroOptions(palette="gameboy", dithering=False))
    con_dither = apply_retro(IMG, RetroOptions(palette="gameboy", dithering=True))
    assert not np.array_equal(sin_dither, con_dither)
    assert _colors(con_dither) <= _palette_colors("gameboy")


def test_paleta_monocromatica_mapea_extremos_de_la_rampa():
    black = synth.solid(24, 24, (0, 0, 0))
    white = synth.solid(24, 24, (255, 255, 255))
    dark = apply_retro(black, RetroOptions(palette="gameboy", dithering=False))
    light = apply_retro(white, RetroOptions(palette="gameboy", dithering=False))
    assert dark[0, 0].tolist() == [15, 56, 15]
    assert light[0, 0].tolist() == [155, 188, 15]


def test_paleta_de_color_respeta_un_color_exacto():
    red = (255, 0, 77)  # #FF004D, rojo de PICO-8
    out = apply_retro(synth.solid(24, 24, red), RetroOptions(palette="pico8", dithering=False))
    assert np.array_equal(out, np.full((24, 24, 3), red, dtype=np.uint8))


def test_apply_retro_no_modifica_la_entrada():
    original = IMG.copy()
    apply_retro(IMG, RetroOptions(palette="virtualboy", dithering=True))
    assert np.array_equal(IMG, original)


def test_apply_retro_opciones_por_defecto():
    assert RetroOptions().palette == "gameboy"
    assert RetroOptions().dithering is True
    out = apply_retro(IMG)
    assert _colors(out) <= _palette_colors("gameboy")


def test_paleta_desconocida():
    with pytest.raises(UnknownPalette, match="Disponibles"):
        apply_retro(IMG, RetroOptions(palette="sega"))
