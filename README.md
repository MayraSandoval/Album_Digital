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

La galería junta ambas carpetas y las muestra separadas por tipo. La página de
búsqueda recorre los originales de `storage/photos/` con histogramas HSV y el
hash perceptual.

## Línea de comandos

```bash
python -m album restore foto.jpg restaurada.png --steps pasos/     # restaura y guarda cada paso
python -m album restore foto.jpg r.png --denoise bilateral         # fuerza un método de denoise
python -m album scan mesa.jpg digitalizada.png                     # endereza una foto impresa
python -m album metrics original.png restaurada.png                # MSE y PSNR
python -m album diagnose foto.jpg                                  # nitidez, ruido y brillo
```

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
    └── tests/                  # los tests de cada TODO + contrato de la API
```

## Integrantes

- Betzabe Mayra, Aldana Sandoval
