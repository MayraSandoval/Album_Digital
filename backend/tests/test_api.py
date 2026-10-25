"""Tests de contrato de la API (todo el flujo del álbum).

"""

from __future__ import annotations

import numpy as np

from album import encode_png
from tests import synth


def _png(image: np.ndarray) -> bytes:
    return encode_png(image)


def _clear_album(client):
    """Deja el álbum vacío: las búsquedas se prueban con estado controlado."""
    for photo in client.get("/api/photos").json():
        client.delete(f"/api/photos/{photo['id']}")
    assert client.get("/api/photos").json() == []


def _upload(client, image: np.ndarray) -> dict:
    response = client.post("/api/photos", files={"file": ("foto.png", _png(image), "image/png")})
    assert response.status_code == 201, response.text
    return response.json()


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_subir_una_foto(client):
    body = _upload(client, synth.photo())
    assert body["width"] == 240 and body["height"] == 180
    assert body["duplicates"] == []
    detail = client.get(f"/api/photos/{body['id']}")
    assert detail.status_code == 200
    media = client.get(body["url"])
    assert media.status_code == 200 and media.headers["content-type"].startswith("image/")


def test_subir_algo_que_no_es_imagen(client):
    response = client.post("/api/photos", files={"file": ("foto.png", b"no soy una imagen", "image/png")})
    assert response.status_code == 422


def test_foto_inexistente(client):
    assert client.get("/api/photos/no-existe").status_code == 404


def test_borrar_una_foto(client):
    body = _upload(client, synth.photo(seed=99))
    assert client.delete(f"/api/photos/{body['id']}").status_code == 204
    assert client.get(f"/api/photos/{body['id']}").status_code == 404


def test_duplicados_al_subir(client):
    image = synth.photo(seed=7)
    first = _upload(client, image)
    second = _upload(client, image.copy())
    assert first["id"] in second["duplicates"]


def test_restaurar_una_foto(client):
    damaged = synth.salt_pepper(synth.scratched(synth.photo(seed=11)))
    body = _upload(client, damaged)
    response = client.post(f"/api/photos/{body['id']}/restore")
    assert response.status_code == 200, response.text
    out = response.json()
    assert [s["name"] for s in out["steps"]] == ["denoise", "scratch_repair", "contrast"]
    assert out["complete"] is True, f"estados: {[(s['name'], s['status']) for s in out['steps']]}"
    media = client.get(out["restored_url"])
    assert media.status_code == 200 and media.headers["content-type"].startswith("image/")


def test_restaurar_con_opciones(client):
    body = _upload(client, synth.photo(seed=12))
    response = client.post(
        f"/api/photos/{body['id']}/restore",
        data={"denoise": "none", "scratches": "false", "contrast": "false"},
    )
    assert response.status_code == 200
    assert response.json()["steps"] == []


def test_diagnosticar_una_foto(client):
    body = _upload(client, synth.salt_pepper(synth.photo(seed=31), amount=0.05))
    response = client.get(f"/api/photos/{body['id']}/diagnose")
    assert response.status_code == 200, response.text
    report = response.json()
    assert set(report) == {"sharpness", "noise", "mean_brightness", "blurry", "noisy"}
    assert report["noisy"] is True


def test_digitalizar_una_foto_impresa(client):
    image, _ = synth.paper_on_table()
    response = client.post("/api/scan", files={"file": ("mesa.png", _png(image), "image/png")})
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "image/png"


def test_digitalizar_sin_hoja(client):
    response = client.post("/api/scan", files={"file": ("mesa.png", _png(synth.plain()), "image/png")})
    assert response.status_code == 422, response.text


def test_buscar_por_color(client):
    _clear_album(client)
    red_id = _upload(client, synth.solid(rgb=(180, 25, 25)))["id"]
    _upload(client, synth.photo(seed=13))
    response = client.get("/api/search/color", params={"hex": "B41919", "min": 0.5})
    assert response.status_code == 200, response.text
    matches = response.json()
    assert matches and matches[0]["photo"]["id"] == red_id
    assert matches[0]["fraction"] > 0.5


def test_buscar_parecidas(client):
    _clear_album(client)
    original = synth.photo(seed=21)
    near = np.clip(original.astype(np.int32) + 15, 0, 255).astype(np.uint8)
    different = synth.solid(rgb=(40, 160, 40))
    original_id = _upload(client, original)["id"]
    near_id = _upload(client, near)["id"]
    _upload(client, different)
    response = client.get(f"/api/search/similar/{original_id}")
    assert response.status_code == 200, response.text
    matches = response.json()
    assert len(matches) == 2, "deberían quedar exactamente dos fotos para comparar"
    assert matches[0]["photo"]["id"] == near_id
    assert matches[0]["distance"] < matches[1]["distance"]
