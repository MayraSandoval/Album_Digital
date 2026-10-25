"""Excepciones de la API.

Mapea las excepciones del core a respuestas HTTP.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from album import AlbumError, DocumentNotFound, InvalidImage, NotImplementedYet


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AlbumError)
    async def album_error(request: Request, exc: AlbumError) -> JSONResponse:
        if isinstance(exc, NotImplementedYet):
            status = 501  # como en el TP-1: la operación existe, pero falta implementarla
        elif isinstance(exc, (InvalidImage, DocumentNotFound)):
            status = 422
        else:
            status = 400
        return JSONResponse(status_code=status, content={"detail": str(exc)})
