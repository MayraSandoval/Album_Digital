"""Schemas de la API (pydantic)."""

from __future__ import annotations

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


class ColorMatchOut(BaseModel):
    photo: PhotoOut
    fraction: float


class SimilarMatchOut(BaseModel):
    photo: PhotoOut
    distance: float
