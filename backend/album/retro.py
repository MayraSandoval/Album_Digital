"""Estilo retro: cuantización con paletas fijas + dithering.

Como lo que hicimoe en el TP-3:

    foto → [GradientMap si la paleta es monocromática] → PaletteMap | FloydSteinberg

- `GradientMap`: pasa la foto a escala de grises y reparte esos grises sobre la
  rampa de colores de la paleta (negro = color más oscuro, blanco = más claro).
  El resultado todavía tiene muchos colores; cuantizarlo es el paso siguiente.
- `PaletteMap`: reemplaza cada píxel por el color más cercano de la paleta
  (distancia euclidiana en RGB; en un empate gana el primero de la lista).
- `Floyd–Steinberg`: igual que PaletteMap, pero reparte el error de cada píxel
  entre los vecinos que faltan visitar: 7/16 a la derecha, 3/16 abajo-izquierda,
  5/16 abajo y 1/16 abajo-derecha.

El dithering se delega a Pillow. Es el mismo algoritmo de difusión de error,
implementado en C: recorrer a mano los 7 millones de píxeles de una foto en
Python tardaría decenas de segundos y la API quedaría trabada. Las paletas y la
cuantización sin dithering sí se implementan acá, paso por paso como en TP-3.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image

from album.exceptions import AlbumError

LUMA = np.array([0.299, 0.587, 0.114], dtype=np.float32)

GRADIENT_CUTOFF = 1.0       # % de píxeles oscuros/claros que se saturan
QUANTIZE_CHUNK = 1 << 17    # píxeles por tanda en la cuantización vectorizada


class UnknownPalette(AlbumError):
    """La paleta pedida no existe."""


@dataclass(frozen=True)
class Palette:
    """Una paleta fija del TP-3."""

    name: str
    label: str
    hex_colors: tuple[str, ...]
    monochrome: bool = False

    @property
    def colors(self) -> np.ndarray:
        """Los colores de la paleta como array (n, 3) uint8."""
        return np.array(
            [[int(color[i : i + 2], 16) for i in (1, 3, 5)] for color in self.hex_colors],
            dtype=np.uint8,
        )

    @property
    def darkest(self) -> np.ndarray:
        colors = self.colors
        return colors[np.argmin(colors.astype(np.float32) @ LUMA)]


PALETTES: dict[str, Palette] = {
    "gameboy": Palette(
        name="gameboy",
        label="Game Boy",
        hex_colors=("#0F380F", "#306230", "#8BAC0F", "#9BBC0F"),
        monochrome=True,
    ),
    "bw": Palette(
        name="bw",
        label="Blanco y negro",
        hex_colors=("#000000", "#FFFFFF"),
        monochrome=True,
    ),
    "virtualboy": Palette(
        name="virtualboy",
        label="Virtual Boy",
        hex_colors=("#000000", "#550000", "#AA0000", "#FF0000"),
        monochrome=True,
    ),
    "cga": Palette(
        name="cga",
        label="CGA",
        hex_colors=("#000000", "#55FFFF", "#FF55FF", "#FFFFFF"),
    ),
    "pico8": Palette(
        name="pico8",
        label="PICO-8",
        hex_colors=(
            "#000000", "#1D2B53", "#7E2553", "#008751",
            "#AB5236", "#5F574F", "#C2C3C7", "#FFF1E8",
            "#FF004D", "#FFA300", "#FFEC27", "#00E436",
            "#29ADFF", "#83769C", "#FF77A8", "#FFCCAA",
        ),
    ),
}

DEFAULT_PALETTE = "gameboy"


@dataclass(frozen=True)
class RetroOptions:
    palette: str = DEFAULT_PALETTE
    dithering: bool = True


def get_palette(name: str) -> Palette:
    try:
        return PALETTES[name]
    except KeyError:
        disponibles = ", ".join(PALETTES)
        raise UnknownPalette(f"Paleta desconocida: {name!r}. Disponibles: {disponibles}.") from None


def nearest_color(color: np.ndarray, colors: np.ndarray) -> np.ndarray:
    """El color de la paleta más cercano a `color` (distancia euclidiana en RGB)."""
    differences = colors.astype(np.float32) - np.asarray(color, dtype=np.float32)
    distances = np.sum(differences**2, axis=1)
    return colors[np.argmin(distances)]


def gradient_map(image: np.ndarray, palette: Palette, cutoff: float = GRADIENT_CUTOFF) -> np.ndarray:
    """Lleva la foto a la rampa de una paleta monocromática (GradientMap de TP-3)."""
    colors = palette.colors.astype(np.float32)
    gray = image.astype(np.float32) @ LUMA

    low, high = np.percentile(gray, [cutoff, 100 - cutoff])
    if high - low >= 1:
        gray = np.clip((gray - low) / (high - low) * 255, 0, 255)

    stops = np.linspace(0, 255, len(colors))
    channels = [np.interp(gray, stops, colors[:, channel]) for channel in range(3)]
    return np.rint(np.stack(channels, axis=-1)).astype(np.uint8)


def palette_map(image: np.ndarray, palette: Palette) -> np.ndarray:
    """Reemplaza cada píxel por el color más cercano de la paleta.

    Se procesa en tandas para no armar una matriz gigante de distancias con
    fotos de varios megapíxeles.
    """
    colors = palette.colors.astype(np.int32)
    pixels = image.reshape(-1, 3).astype(np.int32)
    result = np.empty_like(pixels, dtype=np.uint8)

    for start in range(0, len(pixels), QUANTIZE_CHUNK):
        chunk = pixels[start : start + QUANTIZE_CHUNK]
        differences = chunk[:, None, :] - colors[None, :, :]
        distances = np.einsum("ijk,ijk->ij", differences, differences)
        result[start : start + len(chunk)] = colors[np.argmin(distances, axis=1)]

    return result.reshape(image.shape)


def floyd_steinberg(image: np.ndarray, palette: Palette) -> np.ndarray:
    """Cuantiza con dithering Floyd–Steinberg (7/16, 3/16, 5/16, 1/16)."""
    palette_image = Image.new("P", (1, 1))
    entries = palette.colors.reshape(-1).tolist()
    entries += [0] * (768 - len(entries))
    palette_image.putpalette(entries)

    quantized = Image.fromarray(image, "RGB").quantize(
        palette=palette_image,
        dither=Image.Dither.FLOYDSTEINBERG,
    )
    return np.asarray(quantized.convert("RGB"), dtype=np.uint8).copy()


def apply_retro(image: np.ndarray, options: RetroOptions | None = None) -> np.ndarray:
    """Aplica el estilo retro y devuelve una imagen nueva (no modifica la entrada)."""
    options = options or RetroOptions()
    palette = get_palette(options.palette)

    prepared = gradient_map(image, palette) if palette.monochrome else image.copy()
    if options.dithering:
        return floyd_steinberg(prepared, palette)
    return palette_map(prepared, palette)
