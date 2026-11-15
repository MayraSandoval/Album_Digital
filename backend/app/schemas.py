"""Schemas de la API (pydantic)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ErrorOut(BaseModel):
    detail: str


class PhotoOut(BaseModel):
    id: str
    width: int
    height: int
    mode: str
    size_bytes: int = Field(description="Tamaño del archivo original subido")
    restored: bool = False
    created: str
    duplicates: list[str] = Field(default_factory=list, description="Ids de fotos casi idénticas ya subidas")
    url: str = Field(description="/media/photos/{id}.png")
    restored_url: str | None = None


class StepOut(BaseModel):
    number: int | None
    name: str
    label: str
    status: str
    message: str | None = None


class RestoreOut(BaseModel):
    photo_id: str
    steps: list[StepOut]
    complete: bool
    original_url: str
    restored_url: str | None = None


class DenoiseIn(BaseModel):
    """Parámetros del paso "Quitar ruido" (se aplica uno por vez)."""

    method: Literal["median", "bilateral"] = Field("median", description="Filtro a aplicar")
    kernel_size: int = Field(5, ge=3, le=15, description="Ventana de la mediana (impar)")
    diameter: int = Field(5, ge=3, le=15, description="Vecindad del filtro bilateral (impar)")
    sigma: float = Field(75.0, gt=0, le=200, description="sigmaColor = sigmaSpace del bilateral")

    @field_validator("kernel_size", "diameter")
    @classmethod
    def _must_be_odd(cls, value: int) -> int:
        if value % 2 == 0:
            raise ValueError("tiene que ser impar")
        return value


class ScratchRepairIn(BaseModel):
    """Parámetros del paso "Reparar rasguños"."""

    length: int = Field(25, ge=9, le=51, description="Largo del kernel alargado (impar)")
    min_contrast: int = Field(40, ge=0, le=255, description="Contraste mínimo para creer que hay rayas")
    radius: int = Field(3, ge=1, le=15, description="Radio del inpainting")
    method: Literal["telea", "ns"] = Field("telea", description="Algoritmo de relleno")

    @field_validator("length")
    @classmethod
    def _must_be_odd(cls, value: int) -> int:
        if value % 2 == 0:
            raise ValueError("tiene que ser impar")
        return value


class ContrastIn(BaseModel):
    """Parámetros del paso "Realzar contraste" (CLAHE)."""

    clip_limit: float = Field(2.5, ge=0.5, le=10.0, description="Intensidad del CLAHE")
    tile_size: int = Field(8, ge=2, le=32, description="Lado de la grilla de tiles")


class WhiteBalanceIn(BaseModel):
    """Parámetros del paso "Balance de blancos"."""

    method: Literal["gray-world", "white-patch"] = Field(
        "gray-world", description="gray-world (promedio gris) o white-patch (punto blanco)"
    )
    stretch: bool = Field(True, description="Estirar el histograma del canal L en LAB")


class SharpenIn(BaseModel):
    """Parámetros del paso "Realzar nitidez" (unsharp mask)."""

    amount: float = Field(0.8, ge=0.0, le=2.0, description="Intensidad del realce")
    sigma: float = Field(1.2, gt=0, le=5.0, description="Radio del desenfoque gaussiano")


class RestoreMetricsOut(BaseModel):
    """Comparación de la foto restaurada contra el original."""

    sharpness_before: float
    sharpness_after: float
    noise_before: float
    noise_after: float
    mse: float = Field(description="Error cuadrático medio contra el original")
    psnr: float | None = Field(description="PSNR en dB; None si las imágenes son idénticas")


class ManualRestoreOut(BaseModel):
    photo_id: str
    operation: Literal["denoise", "scratches", "contrast", "whitebalance", "sharpen"]
    label: str
    parameters: dict[str, str | int | float | bool]
    width: int
    height: int
    original_url: str
    restored_url: str
    metrics: RestoreMetricsOut


class QualityOut(BaseModel):
    sharpness: float = Field(description="Varianza del Laplaciano (más alto = más nítida)")
    noise: float = Field(description="Desvío estándar estimado del ruido")
    mean_brightness: float = Field(description="Brillo promedio del gris (0..255)")
    blurry: bool
    noisy: bool


class ColorMatchOut(BaseModel):
    photo: PhotoOut
    fraction: float


class SimilarMatchOut(BaseModel):
    photo: PhotoOut
    distance: float


class PaletteOut(BaseModel):
    name: str
    label: str
    colors: list[str] = Field(description="Colores de la paleta en formato #RRGGBB")
    monochrome: bool


class RetroOut(BaseModel):
    photo_id: str
    palette: str
    palette_label: str
    dithering: bool
    width: int
    height: int
    original_url: str
    url: str


class GalleryItemOut(BaseModel):
    id: str
    kind: Literal["scanned", "restored", "retro"]
    width: int
    height: int
    created: str
    source_id: str | None = Field(
        default=None, description="Foto del álbum de la que salió la restauración o el estilo retro"
    )
    url: str
