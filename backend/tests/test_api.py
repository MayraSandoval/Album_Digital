"""Tests de contrato de la API (todo el flujo del álbum).

Mientras el core tenga partes sin implementar, los endpoints afectados
responden 501: estos tests fallan hasta que implementes cada módulo.
"""

from __future__ import annotations

import io
import json

import numpy as np
from PIL import Image

from album import decode, encode_png, to_pil
from app.config import STORAGE_DIR
from tests import synth


def _png(image: np.ndarray) -> bytes:
    return encode_png(image)


def _png_rotada(image: np.ndarray, orientation: int = 6) -> bytes:
    """PNG con los píxeles girados y la orientación EXIF que anota el celular."""
    exif = Image.Exif()
    exif[274] = orientation
    buffer = io.BytesIO()
    to_pil(image).save(buffer, format="PNG", exif=exif)
    return buffer.getvalue()


def _clear_album(client):
    """Deja el álbum y la galería vacíos: las búsquedas se prueban con estado controlado."""
    for photo in client.get("/api/photos").json():
        client.delete(f"/api/photos/{photo['id']}")
    for item in client.get("/api/gallery").json():
        client.delete(f"/api/gallery/{item['kind']}/{item['id']}")
    client.delete("/api/scrapbook")
    assert client.get("/api/photos").json() == []
    assert client.get("/api/gallery").json() == []
    assert client.get("/api/scrapbook").json()["photos"] == []


def _upload(client, image: np.ndarray) -> dict:
    response = client.post("/api/photos", files={"file": ("foto.png", _png(image), "image/png")})
    assert response.status_code == 201, response.text
    return response.json()


def _make_legacy_restored(photo_id: str) -> None:
    """Restauración del formato viejo: PNG en photos/ y entrada sin restored_url."""
    (STORAGE_DIR / "photos" / f"{photo_id}_restored.png").write_bytes(
        (STORAGE_DIR / "photos" / f"{photo_id}.png").read_bytes()
    )
    entries = json.loads((STORAGE_DIR / "album.json").read_text(encoding="utf-8"))
    for entry in entries:
        if entry["id"] == photo_id:
            entry["restored"] = True
            entry.pop("restored_url", None)
    (STORAGE_DIR / "album.json").write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")


def _retro_items(client, photo_id: str) -> list[dict]:
    return [
        item
        for item in client.get("/api/gallery").json()
        if item["kind"] == "retro" and item["source_id"] == photo_id
    ]


def _retro_path(url: str):
    return STORAGE_DIR / "retro" / url.rsplit("/", 1)[-1]


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


def test_la_orientacion_exif_se_respeta(client):
    upright = synth.photo(width=120, height=200, seed=107)
    sideways = np.ascontiguousarray(np.rot90(upright))  # como lo guarda el celular
    response = client.post(
        "/api/photos", files={"file": ("celular.png", _png_rotada(sideways), "image/png")}
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["width"], body["height"]) == (120, 200)

    stored = decode(client.get(body["url"]).content)
    assert stored.shape[:2] == upright.shape[:2]
    assert np.array_equal(stored, upright)


def test_la_restauracion_conserva_la_orientacion(client):
    upright = synth.photo(width=120, height=200, seed=108)
    body = client.post(
        "/api/photos",
        files={"file": ("celular.png", _png_rotada(np.ascontiguousarray(np.rot90(upright))), "image/png")},
    ).json()
    response = client.post(f"/api/photos/{body['id']}/restore/denoise", json={"method": "median"})
    assert response.status_code == 200, response.text
    restored = decode(client.get(response.json()["restored_url"]).content)
    assert restored.shape[:2] == upright.shape[:2]


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


def test_restaurar_por_paso_ruido(client):
    damaged = synth.salt_pepper(synth.photo(seed=101), amount=0.05)
    body = _upload(client, damaged)
    response = client.post(
        f"/api/photos/{body['id']}/restore/denoise",
        json={"method": "median", "kernel_size": 5},
    )
    assert response.status_code == 200, response.text
    out = response.json()
    assert out["operation"] == "denoise"
    assert out["label"] == "Quitar ruido"
    assert out["parameters"]["method"] == "median"
    assert out["restored_url"] == f"/media/restored/{body['id']}.png"
    assert (STORAGE_DIR / "restored" / f"{body['id']}.png").exists()
    assert client.get(out["restored_url"]).status_code == 200

    saved = [
        item
        for item in client.get("/api/gallery").json()
        if item["kind"] == "restored" and item["source_id"] == body["id"]
    ]
    assert len(saved) == 1


def test_restaurar_por_paso_rasgunos(client):
    body = _upload(client, synth.scratched(synth.photo(seed=102)))
    response = client.post(
        f"/api/photos/{body['id']}/restore/scratches",
        json={"length": 25, "min_contrast": 40, "radius": 3, "method": "ns"},
    )
    assert response.status_code == 200, response.text
    out = response.json()
    assert out["operation"] == "scratches"
    assert out["label"] == "Reparar rasguños"
    assert out["parameters"] == {"length": 25, "min_contrast": 40, "radius": 3, "method": "ns"}
    assert (STORAGE_DIR / "restored" / f"{body['id']}.png").exists()


def test_restaurar_por_paso_contraste(client):
    body = _upload(client, synth.low_contrast(synth.photo(seed=103)))
    response = client.post(
        f"/api/photos/{body['id']}/restore/contrast",
        json={"clip_limit": 4.0, "tile_size": 4},
    )
    assert response.status_code == 200, response.text
    out = response.json()
    assert out["operation"] == "contrast"
    assert out["label"] == "Realzar contraste"
    assert out["parameters"] == {"clip_limit": 4.0, "tile_size": 4}


def test_restaurar_por_paso_balance_de_blancos(client):
    casted = np.clip(
        synth.photo(seed=109).astype(np.float32) * np.array([1.2, 1.0, 0.8]), 0, 255
    ).astype(np.uint8)
    body = _upload(client, casted)
    response = client.post(
        f"/api/photos/{body['id']}/restore/whitebalance",
        json={"method": "gray-world", "stretch": True},
    )
    assert response.status_code == 200, response.text
    out = response.json()
    assert out["operation"] == "whitebalance"
    assert out["label"] == "Balance de blancos"
    assert out["parameters"] == {"method": "gray-world", "stretch": True}
    assert set(out["metrics"]) == {
        "sharpness_before",
        "sharpness_after",
        "noise_before",
        "noise_after",
        "mse",
        "psnr",
    }
    assert out["metrics"]["mse"] > 0


def test_restaurar_por_paso_nitidez(client):
    body = _upload(client, synth.blurred(synth.photo(seed=110)))
    response = client.post(
        f"/api/photos/{body['id']}/restore/sharpen",
        json={"amount": 1.0, "sigma": 1.5},
    )
    assert response.status_code == 200, response.text
    out = response.json()
    assert out["operation"] == "sharpen"
    assert out["label"] == "Realzar nitidez"
    assert out["parameters"] == {"amount": 1.0, "sigma": 1.5}
    assert out["metrics"]["sharpness_after"] > out["metrics"]["sharpness_before"]


def test_los_pasos_nuevos_validan_parametros(client):
    body = _upload(client, synth.photo(seed=111))
    bad_method = client.post(
        f"/api/photos/{body['id']}/restore/whitebalance",
        json={"method": "otro"},
    )
    assert bad_method.status_code == 422
    bad_amount = client.post(
        f"/api/photos/{body['id']}/restore/sharpen",
        json={"amount": 3.0},
    )
    assert bad_amount.status_code == 422
    assert not (STORAGE_DIR / "restored" / f"{body['id']}.png").exists()


def test_restauracion_manual_encadena_y_reemplaza(client):
    damaged = synth.salt_pepper(synth.scratched(synth.photo(seed=104)), amount=0.03)
    body = _upload(client, damaged)
    first = client.post(
        f"/api/photos/{body['id']}/restore/denoise",
        json={"method": "bilateral", "diameter": 5, "sigma": 75},
    )
    assert first.status_code == 200, first.text
    path = STORAGE_DIR / "restored" / f"{body['id']}.png"
    after_first = path.read_bytes()

    second = client.post(
        f"/api/photos/{body['id']}/restore/contrast",
        json={"clip_limit": 3.0, "tile_size": 8},
    )
    assert second.status_code == 200, second.text
    assert second.json()["restored_url"] == first.json()["restored_url"]
    assert path.read_bytes() != after_first, "el segundo paso no partió del primero"

    saved = [
        item
        for item in client.get("/api/gallery").json()
        if item["kind"] == "restored" and item["source_id"] == body["id"]
    ]
    assert len(saved) == 1
    assert client.get(f"/api/photos/{body['id']}").json()["restored"] is True


def test_restauracion_manual_valida_parametros(client):
    body = _upload(client, synth.photo(seed=105))
    even_kernel = client.post(
        f"/api/photos/{body['id']}/restore/denoise",
        json={"method": "median", "kernel_size": 4},
    )
    assert even_kernel.status_code == 422
    unknown_method = client.post(
        f"/api/photos/{body['id']}/restore/denoise",
        json={"method": "gauss"},
    )
    assert unknown_method.status_code == 422
    assert not (STORAGE_DIR / "restored" / f"{body['id']}.png").exists()


def test_descartar_restauracion_manual(client):
    body = _upload(client, synth.photo(seed=106))
    assert client.post(f"/api/photos/{body['id']}/restore/contrast", json={}).status_code == 200
    path = STORAGE_DIR / "restored" / f"{body['id']}.png"
    assert path.exists()

    assert client.delete(f"/api/gallery/restored/{body['id']}").status_code == 204
    assert not path.exists()
    detail = client.get(f"/api/photos/{body['id']}").json()
    assert detail["restored"] is False
    assert detail["restored_url"] is None
    assert client.get(f"/api/photos/{body['id']}").status_code == 200


def test_configuracion_se_guarda_lista_y_borra(client):
    steps = [
        {"operation": "whitebalance", "parameters": {"method": "gray-world", "stretch": False}},
        {"operation": "scratches", "parameters": {"length": 25, "min_contrast": 20, "radius": 1, "method": "telea"}},
    ]
    created = client.post("/api/presets", json={"name": "Receta de prueba", "steps": steps})
    assert created.status_code == 200, created.text
    preset = created.json()
    assert preset["name"] == "Receta de prueba"
    assert [step["operation"] for step in preset["steps"]] == ["whitebalance", "scratches"]
    assert preset["steps"][0]["parameters"] == {"method": "gray-world", "stretch": False}
    assert preset["steps"][1]["parameters"] == {
        "length": 25,
        "min_contrast": 20,
        "radius": 1,
        "method": "telea",
    }
    assert any(item["id"] == preset["id"] for item in client.get("/api/presets").json())

    updated = client.post(
        "/api/presets",
        json={"name": "  RECETA DE PRUEBA ", "steps": [steps[0]]},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["id"] == preset["id"]
    assert len(updated.json()["steps"]) == 1

    assert client.delete(f"/api/presets/{preset['id']}").status_code == 204
    assert all(item["id"] != preset["id"] for item in client.get("/api/presets").json())
    assert client.delete(f"/api/presets/{preset['id']}").status_code == 404


def test_configuracion_valida_parametros(client):
    invalid_contrast = client.post(
        "/api/presets",
        json={"name": "Contraste inválido", "steps": [{"operation": "contrast", "parameters": {"clip_limit": 99}}]},
    )
    assert invalid_contrast.status_code == 422
    empty = client.post("/api/presets", json={"name": "Sin pasos", "steps": []})
    assert empty.status_code == 422
    blank_name = client.post(
        "/api/presets",
        json={"name": "   ", "steps": [{"operation": "contrast", "parameters": {}}]},
    )
    assert blank_name.status_code == 422
    unknown = client.post(
        "/api/presets",
        json={"name": "Operación rara", "steps": [{"operation": "inventada", "parameters": {}}]},
    )
    assert unknown.status_code == 422
    saved = {item["name"] for item in client.get("/api/presets").json()}
    assert not saved & {"Contraste inválido", "Sin pasos", "Operación rara"}


def test_aplicar_configuracion_guardada(client):
    body = _upload(client, synth.low_contrast(synth.scratched(synth.photo(seed=120))))
    steps = [
        {"operation": "whitebalance", "parameters": {"method": "gray-world", "stretch": False}},
        {"operation": "contrast", "parameters": {"clip_limit": 1.5, "tile_size": 8}},
        {"operation": "sharpen", "parameters": {"amount": 0.3, "sigma": 1.5}},
    ]
    preset = client.post("/api/presets", json={"name": "Receta aplicada", "steps": steps}).json()
    try:
        response = client.post(f"/api/photos/{body['id']}/restore/preset/{preset['id']}")
        assert response.status_code == 200, response.text
        out = response.json()
        assert out["preset_name"] == "Receta aplicada"
        assert [step["label"] for step in out["steps"]] == [
            "Balance de blancos",
            "Realzar contraste",
            "Realzar nitidez",
        ]
        assert out["steps"][1]["parameters"] == {"clip_limit": 1.5, "tile_size": 8}
        assert out["restored_url"] == f"/media/restored/{body['id']}.png"
        assert (STORAGE_DIR / "restored" / f"{body['id']}.png").exists()
        assert client.get(out["restored_url"]).status_code == 200
        assert client.get(f"/api/photos/{body['id']}").json()["restored"] is True
        assert out["metrics"]["sharpness_after"] > out["metrics"]["sharpness_before"]
        assert any(
            item["kind"] == "restored" and item["source_id"] == body["id"]
            for item in client.get("/api/gallery").json()
        )
    finally:
        client.delete(f"/api/presets/{preset['id']}")


def test_aplicar_configuracion_inexistente(client):
    body = _upload(client, synth.photo(seed=121))
    response = client.post(f"/api/photos/{body['id']}/restore/preset/no-existe")
    assert response.status_code == 404


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


def test_buscar_por_color_incluye_la_galeria(client):
    _clear_album(client)
    red_id = _upload(client, synth.solid(rgb=(180, 25, 25)))["id"]
    restored = client.post(f"/api/photos/{red_id}/restore")
    assert restored.status_code == 200, restored.text

    response = client.get("/api/search/color", params={"hex": "B41919", "min": 0.5})
    assert response.status_code == 200, response.text
    folders = {(match["photo"]["kind"], match["photo"]["url"].split("/")[2]) for match in response.json()}
    assert ("original", "photos") in folders
    assert ("restored", "restored") in folders


def test_buscar_parecidas_recorre_las_carpetas(client):
    _clear_album(client)
    original_id = _upload(client, synth.photo(seed=77))["id"]
    assert client.post(f"/api/photos/{original_id}/restore").status_code == 200
    retro = client.post(f"/api/photos/{original_id}/retro", data={"palette": "gameboy"})
    assert retro.status_code == 200, retro.text
    image, _ = synth.paper_on_table()
    scanned = client.post("/api/scan", files={"file": ("mesa.png", _png(image), "image/png")})
    assert scanned.status_code == 200, scanned.text

    response = client.get(f"/api/search/similar/{original_id}")
    assert response.status_code == 200, response.text
    matches = response.json()
    assert {match["photo"]["kind"] for match in matches} == {"scanned", "restored", "retro"}
    for match in matches:
        assert match["photo"]["url"].startswith(f"/media/{match['photo']['kind']}/")


def test_digitalizar_guarda_en_su_carpeta(client):
    image, _ = synth.paper_on_table()
    before = {item["id"] for item in client.get("/api/gallery").json()}
    response = client.post("/api/scan", files={"file": ("mesa.png", _png(image), "image/png")})
    assert response.status_code == 200, response.text

    new = [item for item in client.get("/api/gallery").json() if item["kind"] == "scanned" and item["id"] not in before]
    assert len(new) == 1
    item = new[0]
    assert (STORAGE_DIR / "scanned" / f"{item['id']}.png").exists()
    media = client.get(item["url"])
    assert media.status_code == 200 and media.headers["content-type"].startswith("image/")


def test_restaurar_guarda_en_su_carpeta(client):
    body = _upload(client, synth.photo(seed=45))
    response = client.post(f"/api/photos/{body['id']}/restore")
    assert response.status_code == 200, response.text
    out = response.json()
    assert out["restored_url"] == f"/media/restored/{body['id']}.png"
    assert (STORAGE_DIR / "restored" / f"{body['id']}.png").exists()
    assert not (STORAGE_DIR / "photos" / f"{body['id']}_restored.png").exists()

    detail = client.get(f"/api/photos/{body['id']}").json()
    assert detail["restored"] is True
    assert detail["restored_url"] == out["restored_url"]

    saved = [item for item in client.get("/api/gallery").json() if item["kind"] == "restored" and item["source_id"] == body["id"]]
    assert len(saved) == 1
    assert saved[0]["url"] == out["restored_url"]
    assert client.get(saved[0]["url"]).status_code == 200


def test_galeria_separa_digitalizadas_de_restauradas(client):
    _clear_album(client)
    body = _upload(client, synth.photo(seed=51))
    assert client.post(f"/api/photos/{body['id']}/restore").status_code == 200

    image, _ = synth.paper_on_table()
    assert client.post("/api/scan", files={"file": ("mesa.png", _png(image), "image/png")}).status_code == 200

    items = client.get("/api/gallery").json()
    kinds = {item["kind"] for item in items}
    assert {"scanned", "restored"} <= kinds
    assert all(item["url"].startswith("/media/") for item in items)
    restored = [item for item in items if item["kind"] == "restored" and item["source_id"] == body["id"]]
    assert len(restored) == 1
    assert restored[0]["id"] == body["id"]


def test_borrar_foto_borra_su_restauracion(client):
    body = _upload(client, synth.photo(seed=61))
    assert client.post(f"/api/photos/{body['id']}/restore").status_code == 200
    assert client.delete(f"/api/photos/{body['id']}").status_code == 204

    assert not (STORAGE_DIR / "restored" / f"{body['id']}.png").exists()
    saved = [item for item in client.get("/api/gallery").json() if item["source_id"] == body["id"]]
    assert saved == []


def test_galeria_muestra_restauraciones_viejas(client):
    body = _upload(client, synth.photo(seed=71))
    _make_legacy_restored(body["id"])

    legacy_url = f"/media/photos/{body['id']}_restored.png"
    assert client.get(f"/api/photos/{body['id']}").json()["restored_url"] == legacy_url

    saved = [item for item in client.get("/api/gallery").json() if item["kind"] == "restored" and item["source_id"] == body["id"]]
    assert len(saved) == 1
    assert saved[0]["url"] == legacy_url
    assert client.get(legacy_url).status_code == 200


def test_eliminar_digitalizada_de_la_galeria(client):
    image, _ = synth.paper_on_table()
    before = {item["id"] for item in client.get("/api/gallery").json()}
    assert client.post("/api/scan", files={"file": ("mesa.png", _png(image), "image/png")}).status_code == 200

    item = next(
        item for item in client.get("/api/gallery").json() if item["kind"] == "scanned" and item["id"] not in before
    )
    path = STORAGE_DIR / "scanned" / f"{item['id']}.png"
    assert path.exists()

    assert client.delete(f"/api/gallery/scanned/{item['id']}").status_code == 204
    assert not path.exists()
    assert client.delete(f"/api/gallery/scanned/{item['id']}").status_code == 404
    assert all(other["id"] != item["id"] for other in client.get("/api/gallery").json())


def test_eliminar_restaurada_no_borra_la_foto_original(client):
    body = _upload(client, synth.photo(seed=81))
    response = client.post(f"/api/photos/{body['id']}/restore")
    assert response.status_code == 200, response.text
    restored_url = response.json()["restored_url"]

    assert client.delete(f"/api/gallery/restored/{body['id']}").status_code == 204
    assert not (STORAGE_DIR / "restored" / f"{body['id']}.png").exists()
    assert client.get(restored_url).status_code == 404

    detail = client.get(f"/api/photos/{body['id']}")
    assert detail.status_code == 200
    assert detail.json()["restored"] is False
    assert detail.json()["restored_url"] is None
    saved = [item for item in client.get("/api/gallery").json() if item["kind"] == "restored" and item["source_id"] == body["id"]]
    assert saved == []


def test_eliminar_restauracion_vieja_de_la_galeria(client):
    body = _upload(client, synth.photo(seed=82))
    _make_legacy_restored(body["id"])
    legacy_url = f"/media/photos/{body['id']}_restored.png"
    assert client.get(legacy_url).status_code == 200

    assert client.delete(f"/api/gallery/restored/{body['id']}").status_code == 204
    assert not (STORAGE_DIR / "photos" / f"{body['id']}_restored.png").exists()
    assert client.get(legacy_url).status_code == 404

    detail = client.get(f"/api/photos/{body['id']}").json()
    assert detail["restored"] is False
    assert detail["restored_url"] is None
    assert not [item for item in client.get("/api/gallery").json() if item["id"] == body["id"]]


def test_paletas_retro(client):
    response = client.get("/api/retro/palettes")
    assert response.status_code == 200, response.text
    palettes = response.json()
    assert {palette["name"] for palette in palettes} == {"gameboy", "bw", "virtualboy", "cga", "pico8"}
    gameboy = next(palette for palette in palettes if palette["name"] == "gameboy")
    assert gameboy["monochrome"] is True
    assert all(color.startswith("#") and len(color) == 7 for color in gameboy["colors"])


def test_estilo_retro_guarda_en_su_carpeta(client):
    body = _upload(client, synth.photo(seed=91))
    response = client.post(
        f"/api/photos/{body['id']}/retro",
        data={"palette": "gameboy", "dithering": "true"},
    )
    assert response.status_code == 200, response.text
    out = response.json()
    assert out["palette"] == "gameboy"
    assert out["palette_label"] == "Game Boy"
    assert out["dithering"] is True
    assert out["url"].startswith("/media/retro/")
    assert _retro_path(out["url"]).exists()
    assert (STORAGE_DIR / "photos" / f"{body['id']}.png").exists()

    media = client.get(out["url"])
    assert media.status_code == 200 and media.headers["content-type"] == "image/png"

    saved = _retro_items(client, body["id"])
    assert len(saved) == 1
    assert saved[0]["url"] == out["url"]


def test_estilo_retro_acumula_variantes(client):
    body = _upload(client, synth.photo(seed=92))
    first = client.post(f"/api/photos/{body['id']}/retro", data={"palette": "gameboy"}).json()
    first_path = _retro_path(first["url"])
    first_bytes = first_path.read_bytes()

    second = client.post(
        f"/api/photos/{body['id']}/retro",
        data={"palette": "pico8", "dithering": "false"},
    )
    assert second.status_code == 200, second.text
    second = second.json()
    assert second["palette"] == "pico8"
    assert second["dithering"] is False
    assert second["url"] != first["url"]
    second_path = _retro_path(second["url"])
    assert first_path.exists() and second_path.exists()
    assert second_path.read_bytes() != first_bytes

    saved = _retro_items(client, body["id"])
    assert len(saved) == 2
    assert {item["url"] for item in saved} == {first["url"], second["url"]}


def test_estilo_retro_paleta_invalida(client):
    body = _upload(client, synth.photo(seed=93))
    response = client.post(f"/api/photos/{body['id']}/retro", data={"palette": "sega"})
    assert response.status_code == 422, response.text
    assert "Paleta desconocida" in response.json()["detail"]
    assert _retro_items(client, body["id"]) == []


def test_eliminar_retro_no_borra_la_foto_original(client):
    body = _upload(client, synth.photo(seed=94))
    first = client.post(f"/api/photos/{body['id']}/retro", data={"palette": "cga"}).json()
    second = client.post(f"/api/photos/{body['id']}/retro", data={"palette": "bw"}).json()
    first_path = _retro_path(first["url"])
    second_path = _retro_path(second["url"])
    first_item = next(item for item in _retro_items(client, body["id"]) if item["url"] == first["url"])

    assert client.delete(f"/api/gallery/retro/{first_item['id']}").status_code == 204
    assert not first_path.exists()
    assert second_path.exists()
    assert client.get(first["url"]).status_code == 404
    assert client.get(second["url"]).status_code == 200
    assert client.get(f"/api/photos/{body['id']}").status_code == 200

    remaining = _retro_items(client, body["id"])
    assert len(remaining) == 1 and remaining[0]["url"] == second["url"]
    assert client.delete(f"/api/gallery/retro/{first_item['id']}").status_code == 404


def test_borrar_foto_borra_sus_retros(client):
    body = _upload(client, synth.photo(seed=95))
    first = client.post(f"/api/photos/{body['id']}/retro", data={"palette": "bw"}).json()
    second = client.post(f"/api/photos/{body['id']}/retro", data={"palette": "pico8"}).json()
    paths = [_retro_path(first["url"]), _retro_path(second["url"])]
    assert all(path.exists() for path in paths)

    assert client.delete(f"/api/photos/{body['id']}").status_code == 204

    assert not any(path.exists() for path in paths)
    assert _retro_items(client, body["id"]) == []


def test_album_de_recuerdos_guarda_el_nombre(client):
    _clear_album(client)
    body = _upload(client, synth.photo(seed=201))

    created = client.post(
        "/api/scrapbook/photos",
        json={"source_kind": "original", "source_id": body["id"], "name": "  Recién salido del cascarón  "},
    )
    assert created.status_code == 201, created.text
    photo = created.json()
    assert photo["name"] == "Recién salido del cascarón"
    assert photo["kind"] == "original" and photo["source_id"] == body["id"]
    assert photo["url"] == body["url"]

    book = client.get("/api/scrapbook").json()
    assert [item["name"] for item in book["photos"]] == ["Recién salido del cascarón"]
    assert client.get(photo["url"]).status_code == 200


def test_album_acepta_fotos_de_toda_la_galeria(client):
    _clear_album(client)
    body = _upload(client, synth.photo(seed=202))
    restored = client.post(f"/api/photos/{body['id']}/restore/denoise", json={"method": "median"}).json()

    original = client.post(
        "/api/scrapbook/photos",
        json={"source_kind": "original", "source_id": body["id"], "name": "El original"},
    )
    assert original.status_code == 201, original.text

    restaurada = client.post(
        "/api/scrapbook/photos",
        json={"source_kind": "restored", "source_id": body["id"], "name": "La restaurada"},
    )
    assert restaurada.status_code == 201, restaurada.text
    assert restaurada.json()["url"] == restored["restored_url"]
    assert restaurada.json()["kind"] == "restored"

    names = [item["name"] for item in client.get("/api/scrapbook").json()["photos"]]
    assert names == ["El original", "La restaurada"]


def test_album_valida_origen_nombre_y_duplicados(client):
    _clear_album(client)
    body = _upload(client, synth.photo(seed=203))

    vacio = client.post(
        "/api/scrapbook/photos",
        json={"source_kind": "original", "source_id": body["id"], "name": "   "},
    )
    assert vacio.status_code == 422

    inexistente = client.post(
        "/api/scrapbook/photos",
        json={"source_kind": "original", "source_id": "no-existe", "name": "Fantasma"},
    )
    assert inexistente.status_code == 404

    kind_invalido = client.post(
        "/api/scrapbook/photos",
        json={"source_kind": "otra", "source_id": body["id"], "name": "Prueba"},
    )
    assert kind_invalido.status_code == 422

    primero = client.post(
        "/api/scrapbook/photos",
        json={"source_kind": "original", "source_id": body["id"], "name": "Una foto"},
    )
    assert primero.status_code == 201
    repetido = client.post(
        "/api/scrapbook/photos",
        json={"source_kind": "original", "source_id": body["id"], "name": "Otra vez"},
    )
    assert repetido.status_code == 409


def test_album_quita_fotos_y_se_vacia(client):
    _clear_album(client)
    first = _upload(client, synth.photo(seed=204))
    second = _upload(client, synth.photo(seed=205))

    one = client.post(
        "/api/scrapbook/photos",
        json={"source_kind": "original", "source_id": first["id"], "name": "Primera"},
    ).json()
    client.post(
        "/api/scrapbook/photos",
        json={"source_kind": "original", "source_id": second["id"], "name": "Segunda"},
    )

    assert client.delete(f"/api/scrapbook/photos/{one['id']}").status_code == 204
    names = [item["name"] for item in client.get("/api/scrapbook").json()["photos"]]
    assert names == ["Segunda"]
    assert client.delete(f"/api/scrapbook/photos/{one['id']}").status_code == 404

    assert client.delete("/api/scrapbook").status_code == 204
    assert client.get("/api/scrapbook").json()["photos"] == []
    assert client.get(f"/api/photos/{second['id']}").status_code == 200


def test_album_descarta_fotos_que_ya_no_existen(client):
    _clear_album(client)
    body = _upload(client, synth.photo(seed=206))
    client.post(
        "/api/scrapbook/photos",
        json={"source_kind": "original", "source_id": body["id"], "name": "Se va a borrar"},
    )
    assert len(client.get("/api/scrapbook").json()["photos"]) == 1

    assert client.delete(f"/api/photos/{body['id']}").status_code == 204
    assert client.get("/api/scrapbook").json()["photos"] == []
