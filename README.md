# Álbum digital — Trabajo Final Integrador

**Materia:** Técnicas de Procesamiento Digital de Imágenes · 2026

Digitalizá, restaurá y organizá tu álbum de fotos: 
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
- Documentación de la API: http://localhost:8765/docs

Las fotos se guardan en `backend/storage/` (no se sube al repositorio).

## Línea de comandos

```bash
python -m album restore foto.jpg restaurada.png --steps pasos/     # restaura y guarda cada paso
python -m album restore foto.jpg r.png --denoise bilateral         # fuerza un método de denoise
python -m album scan mesa.jpg digitalizada.png                     # endereza una foto impresa
python -m album metrics original.png restaurada.png                # MSE y PSNR
```

## Tests

```bash
cd backend
pytest -v                                  # todo
pytest tests/test_scanning.py -v           # de a un módulo por vez
```

**Estado inicial: los tests de los cuatro TODOs fallan** (responden
`NotImplementedYet`). Este es el punto de partida: implementé cada módulo y ver cómo se ponen verdes.

## Estructura

```
album-digital/
├── README.md
├── informe/INFORME.md          # el informe técnico (se completa en la semana 4)
└── backend/
    ├── requirements.txt
    ├── app/                    # capa de aplicación (API + almacenamiento + frontend)
    │   ├── main.py             # FastAPI
    │   ├── routers/            # photos, restore, scan, search
    │   └── album.py            # índice JSON del álbum
    ├── album/                  # EL CORE: procesamiento puro, reutilizable
    │   ├── imageio.py          #   
    │   ├── pipeline.py         #   
    │   ├── scanning.py         #   
    │   ├── quality.py          #   
    │   ├── restoration.py      #   
    │   └── descriptors.py      #   
    ├── tests/                  # los tests de cada TODO + contrato de la API
    └── frontend/index.html
```


## Integrantes

-Betzabe Mayra, Aldana Sandoval


