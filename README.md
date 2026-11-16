# Álbum digital — Trabajo Final Integrador

**Materia:** Técnicas de Procesamiento Digital de Imágenes · 2026

Digitalizá, restaurá y organizá tu álbum de fotos: la foto impresa de un cajón
pasa por corrección de perspectiva, se le quita el ruido, se le tapan los
rasguños, se le realza el contraste, y queda en un álbum donde se detectan
duplicados y se busca por color o por similitud.

## Cómo correrlo

Requisitos: Python 3.10 o superior.

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows (PowerShell) · Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8765
```

- Frontend: http://localhost:8765
- Galería: http://localhost:8765/galeria.html
- Buscar: http://localhost:8765/buscar.html
- Documentación de la API: http://localhost:8765/docs

Las fotos se guardan en `backend/storage/` (no se sube al repositorio):

| Carpeta | Qué contiene |
|---|---|
| `storage/photos/` | Los originales subidos, con los que trabajan diagnóstico y restauración |
| `storage/scanned/` | Todo lo que pasó por **Digitalizar** |
| `storage/restored/` | Todo lo que pasó por **Restauración** |
| `storage/retro/` | Todo lo que pasó por **4. Estilo retro** |

La galería junta las tres carpetas y las muestra separadas por tipo. La página
de búsqueda recorre **todas las carpetas** de `storage/` (originales,
digitalizadas, restauradas y retro) con histogramas HSV, e indica el tipo de
cada resultado.

## Línea de comandos

```bash
python -m album restore foto.jpg restaurada.png --steps pasos/     # restaura y guarda cada paso
python -m album restore foto.jpg r.png --denoise bilateral         # fuerza un método de denoise
python -m album scan mesa.jpg digitalizada.png                     # endereza una foto impresa
python -m album metrics original.png restaurada.png                # MSE y PSNR
python -m album diagnose foto.jpg                                  # nitidez, ruido y brillo
```

## Restauración manual

La herramienta **3. Restauración** del estudio aplica las técnicas por
separado, como en el TP-1, cada una con sus propios parámetros:

| Paso | Qué hace | Parámetros |
|---|---|---|
| Quitar ruido | mediana (sal y pimienta) o bilateral (ruido fino) | ventana de la mediana; diámetro y sigma del bilateral |
| Reparar rasguños | top-hat alargado + umbral Otsu + inpainting | largo del kernel, contraste mínimo, radio y TELEA/NS |
| Realzar contraste | CLAHE sobre la luminancia | clip limit y grilla de tiles |
| Balance de blancos | gray-world o white patch + estiramiento del canal L en LAB | método y estiramiento on/off |
| Realzar nitidez | unsharp mask (original − versión gaussiana) | intensidad y radio del gaussiano |

Cada paso trabaja sobre el resultado del paso anterior y reemplaza la
restauración de esa foto en `storage/restored/`; la foto original nunca se
modifica. Después de cada paso la API devuelve las métricas frente al
original (nitidez, ruido, MSE y PSNR), que el panel muestra bajo el historial.
"Volver al original" descarta la restauración. La versión automática
(los tres pasos de corrido) sigue disponible en `POST /api/photos/{id}/restore`,
y los pasos manuales en `POST /api/photos/{id}/restore/denoise`,
`.../scratches`, `.../contrast`, `.../whitebalance` y `.../sharpen`.

## Estilo retro

La herramienta **4. Estilo retro** del estudio aplica:
paletas fijas, mapeo de tonos para las paletas monocromáticas y cuantización al
color más cercano. Con el dithering activado, el error de cada píxel se reparte
con Floyd–Steinberg (7/16 a la derecha, 3/16 abajo-izquierda, 5/16 abajo y 1/16
abajo-derecha).

| Paleta | Colores | Tipo |
|---|---|---|
| Game Boy | 4 | monocromática |
| Blanco y negro | 2 | monocromática |
| Virtual Boy | 4 | monocromática |
| CGA | 4 | color |
| PICO-8 | 16 | color |

Los resultados quedan en `storage/retro/` y se pueden borrar desde la galería
sin tocar la foto original. La lista de paletas está en `GET /api/retro/palettes`
y el procesamiento en `POST /api/photos/{id}/retro`.

## Tests

```bash
cd backend
pytest -v                                  # todo
pytest tests/test_scanning.py -v           # de a un módulo por vez
```

## Estructura

```
album-digital/
├── README.md
├── frontend/
│   ├── index.html             # estudio: digitalizar, diagnosticar y restaurar
│   └── galeria.html           # álbum de fotos digitalizadas y restauradas
│   └── buscar.html            # búsqueda por color y por similitud
└── backend/
    ├── requirements.txt
    ├── app/                    # capa de aplicación (API + almacenamiento)
    │   ├── main.py             # FastAPI
    │   ├── routers/            # photos, restore, scan, search, gallery
    │   ├── gallery.py          # carpetas scanned/ y restored/ + índice
    │   └── album.py            # índice JSON del álbum
    ├── album/                  # EL CORE: procesamiento puro, reutilizable
    │   ├── imageio.py          #   
    │   ├── pipeline.py         #   
    │   ├── scanning.py         #   
    │   ├── quality.py          #   
    │   ├── restoration.py      #   
    │   └── descriptors.py      #   
    │   └── retro.py            # estilo retro: paletas, cuantización y dithering    
    └── tests/                  # los tests de cada TODO + contrato de la API
```

## Integrantes

- Betzabe Mayra, Aldana Sandoval
