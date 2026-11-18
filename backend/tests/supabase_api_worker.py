from __future__ import annotations

import json
import os
import sqlite3
import sys

import numpy as np
from fastapi.testclient import TestClient

import app.supabase_client as transport
from album import decode, encode_png
from app.steps import build_step
from tests import synth


class FakeSupabase:
    failing = False

    def __init__(self, url, key, bucket):
        self.path = os.environ["TEST_SUPABASE_DB"]
        with sqlite3.connect(self.path) as db:
            db.execute("create table if not exists records (collection text, id text, unique_key text, data text, primary key (collection, id), unique (collection, unique_key))")
            db.execute("create table if not exists files (folder text, name text, data blob, primary key (folder, name))")

    def _check(self):
        if self.failing:
            raise transport.SupabaseError("fallo simulado")

    def rows(self, collection):
        self._check()
        with sqlite3.connect(self.path) as db:
            rows = db.execute("select data from records where collection = ? order by id", (collection,)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def get(self, collection, item_id):
        self._check()
        with sqlite3.connect(self.path) as db:
            row = db.execute("select data from records where collection = ? and id = ?", (collection, item_id)).fetchone()
        return json.loads(row[0]) if row else None

    def get_unique(self, collection, unique_key):
        self._check()
        with sqlite3.connect(self.path) as db:
            row = db.execute("select data from records where collection = ? and unique_key = ?", (collection, unique_key)).fetchone()
        return json.loads(row[0]) if row else None

    def insert(self, collection, entry, unique_key=None):
        self._check()
        try:
            with sqlite3.connect(self.path) as db:
                db.execute("insert into records values (?, ?, ?, ?)", (collection, entry["id"], unique_key, json.dumps(entry)))
        except sqlite3.IntegrityError:
            raise transport.SupabaseConflict("conflicto simulado") from None

    def upsert(self, collection, entry, unique_key=None):
        self._check()
        try:
            with sqlite3.connect(self.path) as db:
                db.execute("insert into records values (?, ?, ?, ?) on conflict(collection, id) do update set unique_key=excluded.unique_key, data=excluded.data", (collection, entry["id"], unique_key, json.dumps(entry)))
        except sqlite3.IntegrityError:
            raise transport.SupabaseConflict("conflicto simulado") from None

    def delete(self, collection, item_id):
        self._check()
        with sqlite3.connect(self.path) as db:
            return db.execute("delete from records where collection = ? and id = ?", (collection, item_id)).rowcount > 0

    def put_file(self, folder, filename, data):
        self._check()
        with sqlite3.connect(self.path) as db:
            db.execute("insert or replace into files values (?, ?, ?)", (folder, filename, data))

    def get_file(self, folder, filename):
        self._check()
        with sqlite3.connect(self.path) as db:
            row = db.execute("select data from files where folder = ? and name = ?", (folder, filename)).fetchone()
        return row[0] if row else None

    def delete_file(self, folder, filename):
        self._check()
        with sqlite3.connect(self.path) as db:
            db.execute("delete from files where folder = ? and name = ?", (folder, filename))


transport.SupabaseClient = FakeSupabase
from app.main import app
from app.routers.restore import pipeline


with TestClient(app) as client:
    if sys.argv[1] == "create":
        uploaded = client.post("/api/photos", files={"file": ("sintetica.png", encode_png(synth.photo(seed=17)), "image/png")})
        assert uploaded.status_code == 201, uploaded.text
        photo = uploaded.json()
        photo_id = photo["id"]
        first = client.post(f"/api/photos/{photo_id}/restore/denoise", json={"method": "median", "kernel_size": 5})
        assert first.status_code == 200, first.text
        first_image = decode(client.get(first.json()["restored_url"]).content)
        params = {"clip_limit": 3.0, "tile_size": 8}
        expected = pipeline.run(first_image, steps=[build_step("contrast", params)]).image
        second = client.post(f"/api/photos/{photo_id}/restore/contrast", json=params)
        assert second.status_code == 200, second.text
        assert np.array_equal(decode(client.get(second.json()["restored_url"]).content), expected)
        retro = client.post(f"/api/photos/{photo_id}/retro", data={"palette": "gameboy"})
        assert retro.status_code == 200, retro.text
        paper, _ = synth.paper_on_table()
        scan = client.post("/api/scan", files={"file": ("mesa.png", encode_png(paper), "image/png")})
        assert scan.status_code == 200, scan.text
        items = client.get("/api/gallery").json()
        assert {item["kind"] for item in items} == {"scanned", "restored", "retro"}
        assert all(client.get(item["url"]).status_code == 200 for item in items)
        selected = client.post("/api/scrapbook/photos", json={"source_kind": "original", "source_id": photo_id, "name": "Recuerdo"})
        assert selected.status_code == 201, selected.text
        restored_book = client.post("/api/scrapbook/photos", json={"source_kind": "restored", "source_id": photo_id, "name": "Restaurada"})
        assert restored_book.status_code == 201, restored_book.text
        duplicate = client.post("/api/scrapbook/photos", json={"source_kind": "original", "source_id": photo_id, "name": "Otra"})
        assert duplicate.status_code == 409
        preset = client.post("/api/presets", json={"name": "Mi receta", "steps": [{"operation": "contrast", "parameters": params}]})
        assert preset.status_code == 200, preset.text
        matches = client.get(f"/api/search/similar/{photo_id}")
        assert matches.status_code == 200, matches.text
        assert {item["photo"]["kind"] for item in matches.json()} == {"scanned", "restored", "retro"}
        assert client.get("/media/photos/../../secret.png").status_code == 404
        FakeSupabase.failing = True
        failed = client.get("/api/gallery")
        assert failed.status_code == 503 and "fallo simulado" not in failed.text
        FakeSupabase.failing = False
        assert len(client.get("/api/gallery").json()) == 3
    else:
        photos = client.get("/api/photos").json()
        gallery = client.get("/api/gallery").json()
        assert len(photos) == 1 and len(gallery) == 3
        assert photos[0]["restored"] is True
        assert client.get(photos[0]["url"]).status_code == 200
        assert all(client.get(item["url"]).status_code == 200 for item in gallery)
        assert len(client.get("/api/scrapbook").json()["photos"]) == 2
        assert len(client.get("/api/presets").json()) == 1
        assert client.delete(f"/api/gallery/restored/{photos[0]['id']}").status_code == 204
        assert client.get(f"/api/photos/{photos[0]['id']}").json()["restored"] is False
        assert len(client.get("/api/scrapbook").json()["photos"]) == 1
