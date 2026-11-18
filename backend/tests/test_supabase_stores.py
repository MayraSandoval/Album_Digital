"""Contratos de los almacenes remotos, sin red ni credenciales."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier, RLock

import httpx
import numpy as np
import pytest

from album import decode, encode_png
from app.schemas import ContrastIn, DenoiseIn
from app.steps import build_step
from app.supabase_client import SupabaseConflict, SupabaseError
from app.supabase_stores import (
    SupabaseAlbum,
    SupabaseGallery,
    SupabasePresetStore,
    SupabaseScrapbook,
)
from tests import synth


class MemorySupabase:
    """Filas y archivos aislados, con unicidad atómica y fallos inyectables."""

    def __init__(self):
        self._rows = {}
        self._keys = {}
        self._files = {}
        self._lock = RLock()
        self._failures = {}
        self.calls = []
        self.unique_barrier = None

    def fail_next(self, operation, *, after=False):
        with self._lock:
            self._failures[operation] = "after" if after else "before"

    def clear_failures(self):
        with self._lock:
            self._failures.clear()

    def _fail(self, operation, phase):
        if self._failures.get(operation) == phase:
            del self._failures[operation]
            raise SupabaseError(f"fallo temporal de {operation}")

    def rows(self, collection):
        with self._lock:
            self.calls.append(("rows", collection))
            self._fail("rows", "before")
            result = [deepcopy(entry) for (group, _), entry in sorted(self._rows.items()) if group == collection]
            self._fail("rows", "after")
            return result

    def get(self, collection, item_id):
        with self._lock:
            self.calls.append(("get", collection, item_id))
            self._fail("get", "before")
            result = deepcopy(self._rows.get((collection, item_id)))
            self._fail("get", "after")
            return result

    def get_unique(self, collection, unique_key):
        with self._lock:
            self.calls.append(("get_unique", collection, unique_key))
            self._fail("get_unique", "before")
            result = next(
                (deepcopy(self._rows[key]) for key, value in self._keys.items()
                 if key[0] == collection and value == unique_key),
                None,
            )
            self._fail("get_unique", "after")
            barrier = self.unique_barrier if result is None and collection == "presets" else None
        if barrier is not None:
            barrier.wait(timeout=10)
        return result

    def _write_row(self, operation, collection, entry, unique_key):
        with self._lock:
            item = (collection, entry["id"])
            self.calls.append((operation, collection, entry["id"]))
            self._fail(operation, "before")
            collision = unique_key is not None and any(
                key != item and key[0] == collection and value == unique_key
                for key, value in self._keys.items()
            )
            if collision or (operation == "insert" and item in self._rows):
                if operation == "insert":
                    raise SupabaseConflict("409")
                raise SupabaseError("conflicto de unicidad")
            self._rows[item] = deepcopy(entry)
            self._keys[item] = unique_key
            self._fail(operation, "after")

    def insert(self, collection, entry, unique_key=None):
        self._write_row("insert", collection, entry, unique_key)

    def upsert(self, collection, entry, unique_key=None):
        self._write_row("upsert", collection, entry, unique_key)

    def delete(self, collection, item_id):
        with self._lock:
            item = (collection, item_id)
            self.calls.append(("delete", collection, item_id))
            self._fail("delete", "before")
            existed = item in self._rows
            self._rows.pop(item, None)
            self._keys.pop(item, None)
            self._fail("delete", "after")
            return existed

    def put_file(self, folder, filename, data):
        with self._lock:
            self.calls.append(("put_file", folder, filename))
            self._fail("put_file", "before")
            self._files[(folder, filename)] = bytes(data)
            self._fail("put_file", "after")

    def get_file(self, folder, filename):
        with self._lock:
            self.calls.append(("get_file", folder, filename))
            self._fail("get_file", "before")
            result = self._files.get((folder, filename))
            self._fail("get_file", "after")
            return result

    def delete_file(self, folder, filename):
        with self._lock:
            self.calls.append(("delete_file", folder, filename))
            self._fail("delete_file", "before")
            self._files.pop((folder, filename), None)
            self._fail("delete_file", "after")


@pytest.fixture(autouse=True)
def no_http_requests(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Las pruebas no deben realizar solicitudes HTTP")

    monkeypatch.setattr(httpx, "request", forbidden)


@pytest.fixture
def remote():
    return MemorySupabase()


@pytest.fixture
def image():
    return synth.photo(width=96, height=72, seed=42)


def _book_add(book, photo, kind="original", name="Recuerdo"):
    folder = "photos" if kind == "original" else kind
    return book.add(name, kind, photo["id"], folder, photo["filename"], photo["width"], photo["height"])


def test_original_persiste_y_se_recupera_con_instancia_nueva(tmp_path, remote, image):
    png = encode_png(image)
    first = SupabaseAlbum(tmp_path / "primera", remote)
    photo = first.add(png)
    assert (photo["width"], photo["height"], photo["size_bytes"]) == (96, 72, len(png))
    assert photo["restored"] is False
    assert np.array_equal(decode(remote.get_file("photos", photo["filename"])), image)

    recovered = SupabaseAlbum(tmp_path / "segunda", remote)
    assert recovered.get(photo["id"]) == photo
    assert recovered.all() == [photo]
    assert np.array_equal(recovered.read_image(photo), image)
    photo["width"] = 1  # Las respuestas no son referencias a la base de datos.
    assert recovered.get(photo["id"])["width"] == 96
    assert recovered.delete(photo["id"]) is True
    assert recovered.delete(photo["id"]) is False
    assert first.get(photo["id"]) is None
    assert remote.get_file("photos", photo["filename"]) is None


def test_fotos_y_galeria_concurrentes_no_reemplazan_el_indice(tmp_path, remote):
    count = 8
    start = Barrier(count)
    images = [encode_png(synth.photo(width=64, height=48, seed=i)) for i in range(count)]

    def save(index):
        album = SupabaseAlbum(tmp_path / f"proceso-{index}", remote)
        gallery = SupabaseGallery(tmp_path / f"proceso-{index}", remote)
        start.wait(timeout=10)
        photo = album.add(images[index])
        scanned = gallery.add_scanned(images[index], 64, 48)
        restored = gallery.add_restored(photo["id"], images[index], 64, 48)
        album.mark_restored(photo, f"restored/{restored['filename']}")
        return photo, scanned, restored

    with ThreadPoolExecutor(max_workers=count) as executor:
        saved = list(executor.map(save, range(count)))

    album = SupabaseAlbum(tmp_path / "nuevo", remote)
    gallery = SupabaseGallery(tmp_path / "nuevo", remote)
    photos = {entry["id"]: entry for entry in album.all()}
    items = {entry["id"]: entry for entry in gallery.all()}
    assert set(photos) == {photo["id"] for photo, _, _ in saved}
    assert set(items) == {item["id"] for _, scan, restored in saved for item in (scan, restored)}
    for photo, scan, restored in saved:
        assert photos[photo["id"]]["restored"] is True
        assert photos[photo["id"]]["restored_url"] == f"restored/{restored['filename']}"
        assert remote.get_file("scanned", scan["filename"]) is not None
        assert remote.get_file("restored", restored["filename"]) is not None
    assert sum(call[:2] == ("insert", "photos") for call in remote.calls) == count
    assert sum(call[:2] == ("insert", "gallery") for call in remote.calls) == count
    assert sum(call[:2] == ("upsert", "gallery") for call in remote.calls) == count
    assert not list(tmp_path.rglob("*.json"))


def test_restauracion_encadena_pasos_y_sobrevive_a_instancias_nuevas(tmp_path, remote, monkeypatch):
    # La importación del router tampoco debe requerir configuración remota.
    monkeypatch.setenv("ALBUM_STORAGE_BACKEND", "local")
    monkeypatch.delenv("VERCEL", raising=False)
    from app.routers import restore

    image = synth.salt_pepper(synth.photo(width=96, height=72, seed=17), amount=0.12)
    album = SupabaseAlbum(tmp_path / "primera", remote)
    photo = album.add(encode_png(image))
    monkeypatch.setattr(restore, "STORAGE_BACKEND", "supabase")
    monkeypatch.setattr(restore, "album", album)
    monkeypatch.setattr(restore, "gallery", SupabaseGallery(tmp_path / "primera", remote))
    monkeypatch.setattr(restore, "read_media", remote.get_file)
    denoise = DenoiseIn(method="median", kernel_size=3)
    contrast = ContrastIn(clip_limit=2.0, tile_size=4)
    denoise_step = build_step("denoise", denoise.model_dump())
    contrast_step = build_step("contrast", contrast.model_dump())
    expected_first = restore.pipeline.run(image, steps=[denoise_step]).image
    expected_second = restore.pipeline.run(expected_first, steps=[contrast_step]).image
    contrast_original = restore.pipeline.run(image, steps=[contrast_step]).image
    assert not np.array_equal(expected_second, contrast_original)

    first = restore.restore_denoise(photo["id"], denoise)
    first_filename = first.restored_url.rsplit("/", 1)[-1]
    saved_first = remote.get_file("restored", first_filename)
    assert np.array_equal(decode(saved_first), expected_first)
    assert first_filename.startswith(f"{photo['id']}_")

    monkeypatch.setattr(restore, "album", SupabaseAlbum(tmp_path / "segunda", remote))
    monkeypatch.setattr(restore, "gallery", SupabaseGallery(tmp_path / "segunda", remote))
    second = restore.restore_contrast(photo["id"], contrast)
    saved_second = remote.get_file("restored", second.restored_url.rsplit("/", 1)[-1])
    assert np.array_equal(decode(saved_second), expected_second)
    assert second.restored_url != first.restored_url
    assert remote.get_file("restored", first_filename) is None
    entries = SupabaseGallery(tmp_path / "tercera", remote).all()
    assert len([item for item in entries if item["kind"] == "restored" and item["source_id"] == photo["id"]]) == 1
    recovered = SupabaseAlbum(tmp_path / "tercera", remote)
    assert recovered.get(photo["id"])["restored"] is True
    assert np.array_equal(recovered.read_image(photo), image)
    assert restore.gallery.remove_restored(photo["id"]) is True
    recovered.clear_restored(photo["id"])
    assert recovered.get(photo["id"])["restored"] is False
    assert remote.get_file("photos", photo["filename"]) is not None


def test_variantes_retro_se_acumulan_y_se_borran_individualmente(tmp_path, remote, image):
    gallery = SupabaseGallery(tmp_path, remote)
    png = encode_png(image)
    other_png = encode_png(255 - image)
    first = gallery.add_retro("source1", png, 96, 72, "gameboy", True)
    second = gallery.add_retro("source1", other_png, 96, 72, "pico8", False)
    other = gallery.add_retro("source2", png, 96, 72, "bw", False)
    recovered = SupabaseGallery(tmp_path / "nuevo", remote)
    assert len({first["id"], second["id"], other["id"]}) == 3
    assert {entry["id"] for entry in recovered.all()} == {first["id"], second["id"], other["id"]}
    assert (first["palette"], first["dithering"]) == ("gameboy", True)
    assert (second["palette"], second["dithering"]) == ("pico8", False)
    assert remote.get_file("retro", first["filename"]) == png
    assert remote.get_file("retro", second["filename"]) == other_png
    assert recovered.remove_retro_item(first["id"]) is True
    assert recovered.remove_retro_item(first["id"]) is False
    assert remote.get_file("retro", first["filename"]) is None
    assert remote.get_file("retro", second["filename"]) == other_png
    assert recovered.remove_retro("source1") is True
    assert recovered.remove_retro("source1") is False
    assert [entry["id"] for entry in recovered.all()] == [other["id"]]
    assert remote.get_file("retro", other["filename"]) == png


def test_scrapbook_duplicados_por_tipo_y_origen_y_borrado(tmp_path, remote, image):
    photo = SupabaseAlbum(tmp_path, remote).add(encode_png(image))
    book = SupabaseScrapbook(tmp_path, remote)
    original = _book_add(book, photo)
    with pytest.raises(ValueError, match="duplicate"):
        _book_add(SupabaseScrapbook(tmp_path / "otro", remote), photo, name="Otro nombre")
    SupabaseGallery(tmp_path, remote).add_restored(photo["id"], encode_png(image), 96, 72)
    restored = _book_add(book, photo, kind="restored")
    recovered = SupabaseScrapbook(tmp_path / "nuevo", remote)
    assert {entry["id"] for entry in recovered.all()["photos"]} == {original["id"], restored["id"]}
    assert recovered.remove(original["id"]) is True
    assert recovered.remove(original["id"]) is False
    assert recovered.clear() == 1
    assert recovered.clear() == 0
    assert recovered.all()["photos"] == []
    assert remote.get_file("photos", photo["filename"]) is not None


def test_scrapbook_oculta_fotos_borradas_sin_eliminar_sus_referencias(tmp_path, remote, image):
    gallery = SupabaseGallery(tmp_path, remote)
    scanned = gallery.add_scanned(encode_png(image), 96, 72)
    book = SupabaseScrapbook(tmp_path, remote)
    saved = _book_add(book, scanned, kind="scanned")
    assert book.all()["photos"] == [saved]
    assert gallery.remove_scanned(scanned["id"])
    assert book.all()["photos"] == []
    assert remote.get("scrapbook", saved["id"]) == saved


def test_scrapbook_duplicados_concurrentes_solo_guardan_una_fila(tmp_path, remote, image):
    photo = SupabaseAlbum(tmp_path, remote).add(encode_png(image))
    start = Barrier(2)

    def add(index):
        book = SupabaseScrapbook(tmp_path / str(index), remote)
        start.wait(timeout=10)
        try:
            return _book_add(book, photo)
        except ValueError as exc:
            assert str(exc) == "duplicate"
            return None

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(add, range(2)))
    assert sum(result is not None for result in results) == 1
    assert len(SupabaseScrapbook(tmp_path / "nuevo", remote).all()["photos"]) == 1


def test_presets_guardan_actualizan_y_eliminan_por_nombre(tmp_path, remote):
    first_steps = [{"operation": "denoise", "parameters": {"method": "median"}}]
    second_steps = [{"operation": "contrast", "parameters": {"clip_limit": 2.0}}]
    presets = SupabasePresetStore(tmp_path, remote)
    first = presets.save("  Receta Única  ", first_steps)
    assert first["name"] == "Receta Única"
    recovered = SupabasePresetStore(tmp_path / "nuevo", remote)
    assert recovered.get(first["id"])["steps"] == first_steps
    updated = recovered.save(" RECETA ÚNICA ", second_steps)
    assert updated["id"] == first["id"]
    assert updated["created"] == first["created"]
    assert updated["name"] == "RECETA ÚNICA"
    assert recovered.get(first["id"])["steps"] == second_steps
    assert len(recovered.all()) == 1
    assert recovered.delete(first["id"]) is True
    assert recovered.delete(first["id"]) is False
    assert presets.all() == []


def test_presets_concurrentes_resuelven_conflicto_409(tmp_path, remote):
    remote.unique_barrier = Barrier(2)

    def save(index):
        presets = SupabasePresetStore(tmp_path / str(index), remote)
        return presets.save("  RECETA " if index else "receta", [{"operation": str(index)}])

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(save, range(2)))
    assert results[0]["id"] == results[1]["id"]
    saved = SupabasePresetStore(tmp_path / "nuevo", remote).all()
    assert len(saved) == 1
    assert saved[0]["id"] == results[0]["id"]
    assert saved[0]["steps"] in ([{"operation": "0"}], [{"operation": "1"}])


@pytest.mark.parametrize("operation", ["get_file", "delete_file"])
@pytest.mark.parametrize("kind", ["photo", "scanned", "restored", "retro"])
def test_error_temporal_de_storage_no_borra_la_fila(tmp_path, remote, image, operation, kind):
    png = encode_png(image)
    album = SupabaseAlbum(tmp_path, remote)
    gallery = SupabaseGallery(tmp_path, remote)
    if kind == "photo":
        entry = album.add(png)
        remove = lambda: album.delete(entry["id"])
        collection = "photos"
    elif kind == "scanned":
        entry = gallery.add_scanned(png, 96, 72)
        remove = lambda: gallery.remove_scanned(entry["id"])
        collection = "gallery"
    elif kind == "restored":
        entry = gallery.add_restored("source", png, 96, 72)
        remove = lambda: gallery.remove_restored("source")
        collection = "gallery"
    else:
        entry = gallery.add_retro("source", png, 96, 72, "bw", False)
        remove = lambda: gallery.remove_retro_item(entry["id"])
        collection = "gallery"

    remote.fail_next(operation)
    with pytest.raises(SupabaseError):
        remove()
    assert remote.get(collection, entry["id"]) == entry
    assert remote.get_file("photos" if kind == "photo" else kind, entry["filename"]) is not None
    assert remove() is True
    assert remote.get(collection, entry["id"]) is None


def test_estado_restaurado_usa_galeria_y_no_recrea_fotos_borradas(tmp_path, remote, image):
    album = SupabaseAlbum(tmp_path, remote)
    gallery = SupabaseGallery(tmp_path, remote)
    photo = album.add(encode_png(image))
    restored = gallery.add_restored(photo["id"], encode_png(image), 96, 72)
    assert album.get(photo["id"])["restored_url"] == f"restored/{restored['filename']}"
    assert remote.get("photos", photo["id"])["restored"] is False
    assert gallery.remove_restored(photo["id"])
    album.mark_restored(photo, f"restored/{restored['filename']}")
    assert album.get(photo["id"])["restored"] is False
    assert album.delete(photo["id"])
    album.mark_restored(photo, f"restored/{restored['filename']}")
    assert remote.get("photos", photo["id"]) is None


def test_error_ambiguo_al_borrar_archivo_conserva_fila_y_permite_reintento(tmp_path, remote, image):
    gallery = SupabaseGallery(tmp_path, remote)
    entry = gallery.add_scanned(encode_png(image), 96, 72)
    remote.fail_next("delete_file", after=True)
    with pytest.raises(SupabaseError):
        gallery.remove_scanned(entry["id"])
    assert remote.get("gallery", entry["id"]) == entry
    assert remote.get_file("scanned", entry["filename"]) is None
    assert SupabaseGallery(tmp_path / "nuevo", remote).remove_scanned(entry["id"]) is True
    assert remote.get("gallery", entry["id"]) is None


@pytest.mark.parametrize("kind", ["photo", "scanned", "restored", "retro", "preset", "scrapbook"])
def test_error_despues_de_guardar_no_elimina_registro_ni_archivo(tmp_path, remote, image, kind):
    png = encode_png(image)
    album = SupabaseAlbum(tmp_path, remote)
    gallery = SupabaseGallery(tmp_path, remote)
    presets = SupabasePresetStore(tmp_path, remote)
    book = SupabaseScrapbook(tmp_path, remote)
    if kind == "scrapbook":
        photo = album.add(png)
        save = lambda: _book_add(book, photo)
    else:
        save = {
            "photo": lambda: album.add(png),
            "scanned": lambda: gallery.add_scanned(png, 96, 72),
            "restored": lambda: gallery.add_restored("source", png, 96, 72),
            "retro": lambda: gallery.add_retro("source", png, 96, 72, "bw", False),
            "preset": lambda: presets.save("Receta", [{"operation": "denoise"}]),
        }[kind]
    remote.fail_next("upsert" if kind == "restored" else "insert", after=True)
    with pytest.raises(SupabaseError):
        save()

    collection = {"photo": "photos", "preset": "presets", "scrapbook": "scrapbook"}.get(kind, "gallery")
    entries = remote.rows(collection)
    assert len(entries) == 1
    entry = entries[0]
    if kind in {"photo", "scanned", "restored", "retro"}:
        folder = "photos" if kind == "photo" else kind
        data = remote.get_file(folder, entry["filename"])
        assert data is not None and np.array_equal(decode(data), image)
    elif kind == "preset":
        assert presets.save("RECETA", [{"operation": "contrast"}])["id"] == entry["id"]
        assert len(presets.all()) == 1
    else:
        with pytest.raises(ValueError, match="duplicate"):
            _book_add(book, photo)
        assert book.all()["photos"] == [entry]


@pytest.mark.parametrize("kind", ["photo", "gallery", "preset", "scrapbook"])
def test_error_temporal_al_listar_no_descarta_registros(tmp_path, remote, image, kind):
    png = encode_png(image)
    if kind == "photo":
        store = SupabaseAlbum(tmp_path, remote)
        entry = store.add(png)
    elif kind == "gallery":
        store = SupabaseGallery(tmp_path, remote)
        entry = store.add_scanned(png, 96, 72)
    elif kind == "preset":
        store = SupabasePresetStore(tmp_path, remote)
        entry = store.save("Receta", [{"operation": "contrast"}])
    else:
        photo = SupabaseAlbum(tmp_path, remote).add(png)
        store = SupabaseScrapbook(tmp_path, remote)
        entry = _book_add(store, photo)
    collection = {"photo": "photos", "preset": "presets"}.get(kind, kind)
    remote.fail_next("rows")
    try:
        result = store.all()
    except SupabaseError:
        pass  # Propagar el fallo es válido; interpretarlo como colección vacía no.
    else:
        assert entry in (result["photos"] if kind == "scrapbook" else result)
    assert remote.get(collection, entry["id"]) == entry
    result = store.all()
    assert entry in (result["photos"] if kind == "scrapbook" else result)


def test_scrapbook_con_error_temporal_de_archivo_conserva_referencia(tmp_path, remote, image):
    photo = SupabaseAlbum(tmp_path, remote).add(encode_png(image))
    book = SupabaseScrapbook(tmp_path, remote)
    entry = _book_add(book, photo)
    remote.fail_next("get_file")
    try:
        result = book.all()
    except SupabaseError:
        pass
    else:
        assert entry in result["photos"]
    remote.clear_failures()  # all() puede no necesitar consultar Storage.
    assert SupabaseScrapbook(tmp_path / "nuevo", remote).all()["photos"] == [entry]
    assert remote.get("scrapbook", entry["id"]) == entry


@pytest.mark.parametrize("after", [False, True])
def test_error_al_actualizar_restauracion_no_pierde_version_anterior(tmp_path, remote, image, after):
    album = SupabaseAlbum(tmp_path, remote)
    gallery = SupabaseGallery(tmp_path, remote)
    photo = album.add(encode_png(image))
    first = gallery.add_restored(photo["id"], encode_png(image), 96, 72)
    remote.fail_next("upsert", after=after)
    with pytest.raises(SupabaseError):
        gallery.add_restored(photo["id"], encode_png(255 - image), 96, 72)
    assert np.array_equal(decode(remote.get_file("restored", first["filename"])), image)
    current = remote.get("gallery", photo["id"])
    assert (current["filename"] != first["filename"]) is after
    assert album.get(photo["id"])["restored_url"] == f"restored/{current['filename']}"


def test_recuerdo_restaurado_muestra_la_version_actual(tmp_path, remote, image):
    album = SupabaseAlbum(tmp_path, remote)
    gallery = SupabaseGallery(tmp_path, remote)
    book = SupabaseScrapbook(tmp_path, remote)
    photo = album.add(encode_png(image))
    first = gallery.add_restored(photo["id"], encode_png(image), 96, 72)
    book.add("Recuerdo", "restored", photo["id"], first["folder"], first["filename"], 96, 72)
    second = gallery.add_restored(photo["id"], encode_png(255 - image), 96, 72)
    assert book.all()["photos"][0]["filename"] == second["filename"]
    assert book.remove_source("restored", photo["id"]) == 1
    assert book.add("Nuevo", "restored", photo["id"], second["folder"], second["filename"], 96, 72)


def test_borrado_restauracion_se_puede_reintentar(tmp_path, remote, image, monkeypatch):
    from app.routers import gallery as gallery_router

    album = SupabaseAlbum(tmp_path, remote)
    gallery = SupabaseGallery(tmp_path, remote)
    book = SupabaseScrapbook(tmp_path, remote)
    photo = album.add(encode_png(image))
    restored = gallery.add_restored(photo["id"], encode_png(image), 96, 72)
    book.add("Recuerdo", "restored", photo["id"], restored["folder"], restored["filename"], 96, 72)
    monkeypatch.setattr(gallery_router, "STORAGE_BACKEND", "supabase")
    monkeypatch.setattr(gallery_router, "album", album)
    monkeypatch.setattr(gallery_router, "gallery", gallery)
    monkeypatch.setattr(gallery_router, "scrapbook", book)
    remote.fail_next("delete_file")
    with pytest.raises(SupabaseError):
        gallery_router.delete_gallery_item("restored", photo["id"])
    assert album.get(photo["id"])["restored"] is True
    assert gallery_router.delete_gallery_item("restored", photo["id"]).status_code == 204
    assert album.get(photo["id"])["restored"] is False
    assert book.all()["photos"] == []


def test_borrado_original_se_puede_reintentar(tmp_path, remote, image, monkeypatch):
    from app.routers import photos as photos_router

    album = SupabaseAlbum(tmp_path, remote)
    gallery = SupabaseGallery(tmp_path, remote)
    book = SupabaseScrapbook(tmp_path, remote)
    photo = album.add(encode_png(image))
    gallery.add_restored(photo["id"], encode_png(image), 96, 72)
    _book_add(book, photo)
    monkeypatch.setattr(photos_router, "STORAGE_BACKEND", "supabase")
    monkeypatch.setattr(photos_router, "album", album)
    monkeypatch.setattr(photos_router, "gallery", gallery)
    monkeypatch.setattr(photos_router, "scrapbook", book)
    remote.fail_next("delete_file")
    with pytest.raises(SupabaseError):
        photos_router.delete_photo(photo["id"])
    assert album.get(photo["id"]) is not None
    photos_router.delete_photo(photo["id"])
    assert album.get(photo["id"]) is None
    assert gallery.all() == []
    assert book.all()["photos"] == []


def test_listar_fotos_consulta_las_colecciones_una_sola_vez(tmp_path, remote, image, monkeypatch):
    from app.routers import photos as photos_router

    album = SupabaseAlbum(tmp_path, remote)
    for seed in range(4):
        album.add(encode_png(synth.photo(width=96, height=72, seed=seed)))
    monkeypatch.setattr(photos_router, "album", album)
    remote.calls.clear()
    assert len(photos_router.list_photos()) == 4
    assert remote.calls.count(("rows", "photos")) == 1
    assert remote.calls.count(("rows", "gallery")) == 1
