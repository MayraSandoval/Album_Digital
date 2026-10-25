"""Lectura de archivos subidos."""

from __future__ import annotations

from fastapi import UploadFile

from app.config import MAX_UPLOAD_BYTES
from album import InvalidImage


async def read_upload(file: UploadFile) -> bytes:
    """Lee el archivo subido y valida tamaño y contenido mínimo."""
    data = await file.read()
    if not data:
        raise InvalidImage("El archivo está vacío.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise InvalidImage(f"El archivo supera los {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
    return data
