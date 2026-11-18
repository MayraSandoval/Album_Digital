from __future__ import annotations

import httpx
import pytest

from app.supabase_client import SupabaseClient, SupabaseConflict, SupabaseError


@pytest.mark.parametrize("key,authorization", [("sb_secret_test", None), ("legacy-jwt", "Bearer legacy-jwt")])
def test_authentication_and_private_storage_endpoint(monkeypatch, key, authorization):
    calls = []

    def request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return httpx.Response(200, content=b"imagen")

    monkeypatch.setattr(httpx, "request", request)
    client = SupabaseClient("https://example.supabase.co", key, "album-fotos")
    assert client.get_file("photos", "0123456789ab.png") == b"imagen"
    method, url, options = calls[0]
    assert method == "GET"
    assert url.endswith("/storage/v1/object/authenticated/album-fotos/photos/0123456789ab.png")
    assert options["headers"]["apikey"] == key
    assert options["headers"].get("Authorization") == authorization
    assert options["follow_redirects"] is False


def test_list_paginates_when_server_truncates(monkeypatch):
    entries = [{"id": str(i)} for i in range(5)]
    offsets = []

    def request(method, url, **kwargs):
        offset = kwargs["params"]["offset"]
        offsets.append(offset)
        page = entries[offset:offset + 2]
        return httpx.Response(200, headers={"content-range": f"{offset}-{offset + len(page) - 1}/5"},
                              json=[{"data": entry} for entry in page])

    monkeypatch.setattr(httpx, "request", request)
    assert SupabaseClient("https://example.supabase.co", "key", "album-fotos").rows("photos") == entries
    assert offsets == [0, 2, 4]


def test_missing_file_is_not_a_transient_error(monkeypatch):
    client = SupabaseClient("https://example.supabase.co", "key", "album-fotos")
    monkeypatch.setattr(httpx, "request", lambda *args, **kwargs: httpx.Response(404, json={"code": "NoSuchKey"}))
    assert client.get_file("photos", "0123456789ab.png") is None
    monkeypatch.setattr(httpx, "request", lambda *args, **kwargs: httpx.Response(404, json={"code": "NoSuchBucket"}))
    with pytest.raises(SupabaseError):
        client.get_file("photos", "0123456789ab.png")
    monkeypatch.setattr(httpx, "request", lambda *args, **kwargs: httpx.Response(503, text="private server details"))
    with pytest.raises(SupabaseError, match="Supabase") as error:
        client.get_file("photos", "0123456789ab.png")
    assert "private server details" not in str(error.value)


def test_network_errors_and_conflicts_do_not_expose_secrets(monkeypatch):
    client = SupabaseClient("https://example.supabase.co", "sb_secret_test", "album-fotos")

    def fail(*args, **kwargs):
        raise httpx.ConnectError("sb_secret_test")

    monkeypatch.setattr(httpx, "request", fail)
    with pytest.raises(SupabaseError) as error:
        client.rows("photos")
    assert "sb_secret_test" not in str(error.value)
    assert error.value.__context__ is None
    monkeypatch.setattr(httpx, "request", lambda *args, **kwargs: httpx.Response(409))
    with pytest.raises(SupabaseConflict):
        client.insert("photos", {"id": "0123456789ab"})


@pytest.mark.parametrize("url", ["http://example.com", "https://user:pass@example.com", "https://example.com/path"])
def test_rejects_unsafe_project_url(url):
    with pytest.raises(ValueError):
        SupabaseClient(url, "key", "album-fotos")


def test_rejects_unsafe_object_paths():
    client = SupabaseClient("https://example.supabase.co", "key", "album-fotos")
    for folder, filename in [("../photos", "0123456789ab.png"), ("photos", "../secret.png")]:
        with pytest.raises(ValueError):
            client.get_file(folder, filename)
