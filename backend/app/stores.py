from __future__ import annotations

from app.album import Album
from app.config import STORAGE_BACKEND, STORAGE_DIR, SUPABASE_BUCKET, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL
from app.gallery import Gallery
from app.presets import PresetStore
from app.scrapbook import Scrapbook

if STORAGE_BACKEND == "supabase":
    from app.supabase_client import SupabaseClient
    from app.supabase_stores import SupabaseAlbum, SupabaseGallery, SupabasePresetStore, SupabaseScrapbook

    supabase = SupabaseClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_BUCKET)
    album = SupabaseAlbum(STORAGE_DIR, supabase)
    gallery = SupabaseGallery(STORAGE_DIR, supabase)
    presets = SupabasePresetStore(STORAGE_DIR, supabase)
    scrapbook = SupabaseScrapbook(STORAGE_DIR, supabase)
else:
    supabase = None
    album = Album(STORAGE_DIR)
    gallery = Gallery(STORAGE_DIR)
    presets = PresetStore(STORAGE_DIR)
    scrapbook = Scrapbook(STORAGE_DIR)


def read_media(folder: str, filename: str) -> bytes | None:
    if supabase is not None:
        return supabase.get_file(folder, filename)
    path = STORAGE_DIR / folder / filename
    return path.read_bytes() if path.is_file() else None
