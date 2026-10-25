"""Aplicación web del álbum.

Sirve el frontend y la API; el procesamiento vive en el paquete `album`
(el core), que también se usa desde la consola (`python -m album`).
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import FRONTEND_DIR, MEDIA_URL, PHOTOS_DIR, STORAGE_DIR
from app.errors import register_exception_handlers
from app.routers import photos, restore, scan, search


@asynccontextmanager
async def lifespan(app: FastAPI):
    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title="Álbum Digital — Trabajo Final Integrador",
    description="Digitalizá, restaurá y organizá tu álbum de fotos con técnicas de procesamiento digital de imágenes.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)


@app.get("/api/health", tags=["system"], summary="Estado del servidor")
def health():
    return {"status": "ok"}


app.include_router(photos.router)
app.include_router(restore.router)
app.include_router(scan.router)
app.include_router(search.router)

# Archivos de fotos en disco.
PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
app.mount(MEDIA_URL, StaticFiles(directory=STORAGE_DIR), name="media")

# El frontend se monta al final porque captura "/".
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
