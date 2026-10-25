"""Fixture compartida: la API corriendo contra un almacenamiento temporal.

El entorno se configura ANTES de importar `app` para que STORAGE_DIR apunte
a una carpeta temporal (ver app/config.py).
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

os.environ["ALBUM_STORAGE"] = str(Path(tempfile.mkdtemp(prefix="album-tests-")))

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client
