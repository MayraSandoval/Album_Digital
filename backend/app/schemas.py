"""Schemas de la API (pydantic)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


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
