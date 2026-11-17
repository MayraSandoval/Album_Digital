import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "backend"))

os.environ.setdefault("ALBUM_STORAGE", "/tmp/album-storage")

from app.main import app  # noqa: E402,F401
