"""Adaptador HTTP de servidor para PostgREST y Supabase Storage privado."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit

import httpx


class SupabaseError(Exception):
    """Error de comunicación o respuesta de Supabase sin detalles sensibles."""


class SupabaseConflict(SupabaseError):
    """La inserción entra en conflicto con un registro existente."""


class SupabaseClient:
    _PAGE_SIZE = 1000
    _TIMEOUT = 20.0
    _FOLDERS = frozenset({"photos", "scanned", "restored", "retro"})
    _FILENAME = re.compile(r"[0-9a-f]{12}(?:_[0-9a-f]{12}|_restored)?\.png")
    _BUCKET = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}")

    def __init__(self, url: str, key: str, bucket: str) -> None:
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
                or parsed.password is not None or parsed.path not in {"", "/"} or parsed.query or parsed.fragment):
            raise ValueError("SUPABASE_URL debe ser la dirección HTTPS del proyecto.")
        if not isinstance(bucket, str) or not self._BUCKET.fullmatch(bucket):
            raise ValueError("Nombre de bucket inválido.")
        self._url = url.rstrip("/")
        self._key = key
        self._bucket = bucket

    def _request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        conflict_on_409: bool = False,
        allow_404: bool = False,
        **kwargs: Any,
    ) -> httpx.Response:
        request_headers = {"apikey": self._key}
        if not self._key.startswith("sb_secret_"):
            request_headers["Authorization"] = f"Bearer {self._key}"
        if headers:
            request_headers.update(headers)
        try:
            response = httpx.request(
                method,
                f"{self._url}{path}",
                headers=request_headers,
                timeout=self._TIMEOUT,
                follow_redirects=False,
                **kwargs,
            )
        except (httpx.HTTPError, httpx.InvalidURL):
            response = None

        # Se lanza fuera del except para no adjuntar la excepción HTTP original.
        if response is None:
            raise SupabaseError("No se pudo conectar con Supabase.")
        if response.status_code == 404 and allow_404:
            return response
        if response.status_code == 409 and conflict_on_409:
            raise SupabaseConflict("Conflicto al insertar el registro.")
        if not 200 <= response.status_code < 300:
            raise SupabaseError("La operación de Supabase falló.")
        return response

    @staticmethod
    def _json_list(response: httpx.Response) -> list[dict]:
        try:
            value = response.json()
        except ValueError:
            value = None
        if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
            raise SupabaseError("Respuesta inválida de Supabase.")
        return value

    @classmethod
    def _entries(cls, response: httpx.Response) -> list[dict]:
        records = cls._json_list(response)
        if any(not isinstance(record.get("data"), dict) for record in records):
            raise SupabaseError("Respuesta inválida de Supabase.")
        return [record["data"] for record in records]

    @staticmethod
    def _total(response: httpx.Response) -> int | None:
        content_range = response.headers.get("content-range", "")
        _, separator, total = content_range.rpartition("/")
        if separator and total.isascii() and total.isdecimal():
            return int(total)
        return None

    @staticmethod
    def _record(collection: str, entry: dict, unique_key: str | None) -> dict:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str) or not entry["id"]:
            raise ValueError("La entrada debe tener un id de texto.")
        return {
            "collection": collection,
            "item_id": entry["id"],
            "unique_key": unique_key,
            "data": entry,
        }

    def rows(self, collection: str) -> list[dict]:
        entries: list[dict] = []
        offset = 0
        while True:
            response = self._request(
                "GET",
                "/rest/v1/album_records",
                headers={"Prefer": "count=exact"},
                params={
                    "select": "data",
                    "collection": f"eq.{collection}",
                    "order": "item_id.asc",
                    "limit": self._PAGE_SIZE,
                    "offset": offset,
                },
            )
            page = self._entries(response)
            if not page:
                break
            entries.extend(page)
            offset += len(page)
            total = self._total(response)
            if total is not None and offset >= total:
                break
        return entries

    def get(self, collection: str, item_id: str) -> dict | None:
        response = self._request(
            "GET",
            "/rest/v1/album_records",
            params={
                "select": "data",
                "collection": f"eq.{collection}",
                "item_id": f"eq.{item_id}",
                "limit": 1,
            },
        )
        entries = self._entries(response)
        return entries[0] if entries else None

    def get_unique(self, collection: str, unique_key: str) -> dict | None:
        response = self._request(
            "GET",
            "/rest/v1/album_records",
            params={
                "select": "data",
                "collection": f"eq.{collection}",
                "unique_key": f"eq.{unique_key}",
                "limit": 1,
            },
        )
        entries = self._entries(response)
        return entries[0] if entries else None

    def insert(self, collection: str, entry: dict, unique_key: str | None = None) -> None:
        self._request(
            "POST",
            "/rest/v1/album_records",
            headers={"Prefer": "return=minimal"},
            json=self._record(collection, entry, unique_key),
            conflict_on_409=True,
        )

    def upsert(self, collection: str, entry: dict, unique_key: str | None = None) -> None:
        self._request(
            "POST",
            "/rest/v1/album_records",
            headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
            params={"on_conflict": "collection,item_id"},
            json=self._record(collection, entry, unique_key),
        )

    def delete(self, collection: str, item_id: str) -> bool:
        response = self._request(
            "DELETE",
            "/rest/v1/album_records",
            headers={"Prefer": "return=representation"},
            params={"collection": f"eq.{collection}", "item_id": f"eq.{item_id}"},
        )
        return bool(self._json_list(response))

    def _file_path(self, folder: str, filename: str) -> str:
        if not isinstance(folder, str) or folder not in self._FOLDERS:
            raise ValueError("Carpeta de Storage inválida.")
        if not isinstance(filename, str) or not self._FILENAME.fullmatch(filename):
            raise ValueError("Nombre de archivo de Storage inválido.")
        return f"{folder}/{filename}"

    def put_file(self, folder: str, filename: str, data: bytes) -> None:
        path = self._file_path(folder, filename)
        self._request(
            "POST",
            f"/storage/v1/object/{self._bucket}/{path}",
            headers={"Content-Type": "image/png", "x-upsert": "true"},
            content=data,
        )

    def get_file(self, folder: str, filename: str) -> bytes | None:
        path = self._file_path(folder, filename)
        response = self._request(
            "GET",
            f"/storage/v1/object/authenticated/{self._bucket}/{path}",
            allow_404=True,
        )
        if response.status_code == 404:
            try:
                error = response.json()
            except ValueError:
                error = None
            if isinstance(error, dict) and error.get("code") == "NoSuchKey":
                return None
            raise SupabaseError("No se pudo acceder al almacenamiento de Supabase.")
        return response.content

    def delete_file(self, folder: str, filename: str) -> None:
        path = self._file_path(folder, filename)
        self._request(
            "DELETE",
            f"/storage/v1/object/{self._bucket}",
            json={"prefixes": [path]},
        )
