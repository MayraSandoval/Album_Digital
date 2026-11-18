"""Aplicación web del álbum. Dado.

Sirve el frontend y la API; el procesamiento vive en el paquete `album`
(el core), que también se usa desde la consola (`python -m album`).
"""

from contextlib import asynccontextmanager
import re

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import FRONTEND_DIR, MEDIA_URL, PHOTOS_DIR, RESTORED_DIR, RETRO_DIR, SCANNED_DIR, STORAGE_BACKEND, STORAGE_DIR
from app.errors import register_exception_handlers
from app.routers import gallery, photos, presets, restore, retro, scan, scrapbook, search
from app.stores import read_media


@asynccontextmanager
async def lifespan(app: FastAPI):
    if STORAGE_BACKEND == "local":
        for folder in (PHOTOS_DIR, SCANNED_DIR, RESTORED_DIR, RETRO_DIR):
            folder.mkdir(parents=True, exist_ok=True)
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
app.include_router(presets.router)
app.include_router(restore.router)
app.include_router(retro.router)
app.include_router(scan.router)
app.include_router(search.router)
app.include_router(scrapbook.router)
app.include_router(gallery.router)

if STORAGE_BACKEND == "local":
    for folder in (PHOTOS_DIR, SCANNED_DIR, RESTORED_DIR, RETRO_DIR):
        folder.mkdir(parents=True, exist_ok=True)
    app.mount(MEDIA_URL, StaticFiles(directory=STORAGE_DIR), name="media")
else:
    from app.supabase_client import SupabaseError

    @app.exception_handler(SupabaseError)
    async def supabase_error(request: Request, exc: SupabaseError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": "El almacenamiento no está disponible. Intentá nuevamente."})

    @app.get(f"{MEDIA_URL}/{{folder}}/{{filename}}", include_in_schema=False)
    def media(folder: str, filename: str):
        if folder not in {"photos", "scanned", "restored", "retro"} or not re.fullmatch(
            r"[0-9a-f]{12}(?:_[0-9a-f]{12}|_restored)?\.png", filename
        ):
            raise HTTPException(status_code=404, detail="Imagen no encontrada.")
        data = read_media(folder, filename)
        if data is None:
            raise HTTPException(status_code=404, detail="Imagen no encontrada.")
        return Response(data, media_type="image/png", headers={"Cache-Control": "no-store"})

# El frontend se monta al final porque captura "/".
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
