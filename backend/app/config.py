"""Configuración de la capa de aplicación. Dado.

`ALBUM_STORAGE` (variable de entorno) permite apuntar el almacenamiento a
otra carpeta — la usan los tests para no tocar tus fotos.
"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/

FRONTEND_DIR = BASE_DIR.parent / "frontend"  # raíz del repo, fuera de backend/
STORAGE_DIR = Path(os.environ.get("ALBUM_STORAGE", str(BASE_DIR / "storage")))
PHOTOS_DIR = STORAGE_DIR / "photos"
INDEX_PATH = STORAGE_DIR / "album.json"

MEDIA_URL = "/media"
MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB
