# Álbum Digital BMAS — Trabajo Final Integrador

**Materia:** Técnicas de Procesamiento Digital de Imágenes<br>
**Año y cuatrimestre de cursada:** 2026 2C<br>
**Nombres y Apellidos:** Betzabe Mayra, Aldana Sandoval<br>
**Docente:** Juan Ignacio, Bonini<br>

---

## Motivo de la creación de la App

### Resolver un problema cotidiano con fotos impresas
Digitalizár, restaurár y organizár tu álbum de fotos: la foto impresa de un cajón
pasa por corrección de perspectiva, se le quita el ruido, se le tapan los
rasguños, se le realza el contraste, y queda en un álbum donde se detectan
duplicados y se busca por color o por similitud.

### Integrar todo el temario de la materia
El proyecto buscó unir en una sola aplicación la mayor parte de los ejercicios y los trabajos prácticos vistos, poniendo especial foco en las unidades de restauración y análisis, 
en los descriptores y reconocimiento.

### Priorizar técnicas clásicas y medibles
Elegí construir un núcleo propio en Python y OpenCV en lugar de usar modelos preentrenados de caja negra, para poder justificar cada algoritmo con métricas objetivas (MSE, PSNR, nitidez y ruido). 

---

## Problemáticas encontradas y cómo las resolví

### Procesamiento digital de imágenes

**La restauración automática no funcionaba bien en las fotos**<br>
A partir de la devolución del docente, se comprobó que una sola pasada automática aplicaba filtros innecesarios y no corregía dominantes de color. 

Se pasó a un esquema de restauración manual paso por paso, con parámetros visibles, métricas antes/después, se creo un botón para volver al original y otro para las configuraciones guardadas (presets) reutilizables. 
También se sumaron dos pasos nuevos: balance de blancos (gray-world / white-patch) y realce de nitidez (unsharp mask). 

**El escáner fallaba sobre fondos texturados**<br>
Al probar con fotos reales apoyadas sobre un mantel con textura, Canny no lograba cerrar el borde de la hoja y devolvía un contorno inválido de 10 vértices. 

Se incorporó una segunda pasada de respaldo con GrabCut, fijando la semilla (cv2.setRNGSeed(0)) para garantizar resultados deterministas y descartando cuadriláteros degenerados. 

**El reparador de rasguños borraba la mirada y las cejas**<br>
En los rostros de la foto, el detector morfológico confundía los brillos pequeños de ojos, párpados y cejas con rayas blancas y los rellenaba con inpainting. 

Se eliminó la dilatación 3×3 y se filtraron los componentes pequeños de la máscara (menores a 50 px o al 0,01 % del área en fotos grandes), logrando tapar las rayas largas sin dañar los rasgos faciales. 

### Despliegue en la nube (Vercel y Supabase)

**Tamaño del paquete excedido (832,54 MB > 500 MB)**<br>
Al desplegar con includeFiles: "**", Vercel incluía el entorno virtual y cachés internas, superando el límite permitido para funciones Python. 

Se restringió includeFiles únicamente a "{backend,frontend}/**" en vercel.json. 

**Error 413 al subir o recortar fotos grandes**<br>
Vercel impone un límite de 4,5 MB por solicitud y respuesta, por lo que los archivos originales o el PNG recortado fallaban al enviarse a /api/photos. 

Se implementó una reducción automática en el navegador (máximo 1000 px por lado) sobre una copia de trabajo antes de subirla, y se aplicó el mismo límite al PNG devuelto por el escáner. 

**Pérdida de la galería y fallos de descarga por almacenamiento efímero**<br>
En Vercel el almacenamiento local vive en /tmp y se borra al reiniciarse la función, lo que hacía fallar la descarga de la imagen procesada y vaciaba la galería. 

Se modificó la descarga para que use una copia ya cargada en el navegador y se integró Supabase Storage (con bucket privado) y PostgreSQL para dar persistencia real a las fotos y a los índices del álbum. 


## Cómo correrlo

Requisitos: Python 3.10 o superior.

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows (PowerShell) · Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8765
```

- **Estudio (Frontend):** http://localhost:8765
- **Galería:** http://localhost:8765/galeria.html
- **Álbum de recuerdos:** http://localhost:8765/album.html
- **Buscar:** http://localhost:8765/buscar.html

Las fotos se guardan en `backend/storage/` (no se sube al repositorio):

| Carpeta | Qué contiene |
|---|---|
| `storage/photos/` | Los originales subidos, con los que trabajan diagnóstico y restauración |
| `storage/scanned/` | Todo lo que pasó por **Digitalizar** |
| `storage/restored/` | Todo lo que pasó por **Restauración** |
| `storage/retro/` | Todo lo que pasó por **Estilo retro**  (acumulables por paleta) |
| `album.json`, `gallery.json`, `presets.json`, `scrapbook.json` | Índices de fotos, galería, configuraciones guardadas y álbum de recuerdos |


La galería muestra los originales y los resultados agrupados por tipo, permite eliminarlos con confirmación sin tocar el original y agregarlos al **Álbum de recuerdos** con un nombre elegido por el usuario. La página de búsqueda recorre **todas las carpetas** de `storage/` con histogramas HSV e indica el tipo de cada resultado.

## Línea de comandos

```bash
python -m album restore foto.jpg restaurada.png --steps pasos/     # restaura y guarda cada paso
python -m album restore foto.jpg r.png --denoise bilateral         # fuerza un método de denoise
python -m album scan mesa.jpg digitalizada.png                     # endereza una foto impresa
python -m album metrics original.png restaurada.png                # MSE y PSNR
python -m album diagnose foto.jpg                                  # nitidez, ruido y brillo
```

## Restauración manual y configuraciones guardadas (Presets)

La herramienta **Restauración** del estudio aplica cada técnica por separado, con parámetros visibles y métricas de control:

| Paso | Qué hace | Parámetros |
|---|---|---|
| Quitar ruido | Mediana (sal y pimienta) o bilateral (ruido fino) | Ventana de la mediana; diámetro y sigma del bilateral |
| Reparar rasguños | Top-hat alargado + umbral Otsu + filtrado de componentes + *inpainting* | Largo del kernel, contraste mínimo, radio y método (TELEA/NS) |
| Realzar contraste | CLAHE sobre el canal L en espacio LAB | Clip limit y grilla de tiles |
| Balance de blancos | *Gray-world* o *white-patch* + estiramiento del canal L en LAB | Método y estiramiento activado/desactivado |
| Realzar nitidez | *Unsharp mask* (original − versión gaussiana) | Intensidad y radio (sigma) |

Cada paso trabaja sobre el resultado del paso anterior y reemplaza la restauración de esa foto en `storage/restored/`; la foto original nunca se modifica. Después de cada paso la API devuelve las métricas frente al original (nitidez, ruido, MSE y PSNR). El botón **Volver al original** descarta la restauración actual.

Además, el usuario puede **guardar la secuencia de pasos aplicada como una configuración (*preset*)** con un nombre propio y reutilizarla en un solo clic sobre fotografías similares (`GET/POST /api/presets`, `DELETE /api/presets/{id}`, `POST /api/photos/{id}/restore/preset/{preset_id}`).

La versión automática (tres pasos encadenados) sigue disponible en `POST /api/photos/{id}/restore`, y los pasos manuales en `POST /api/photos/{id}/restore/{denoise|scratches|contrast|whitebalance|sharpen}`.

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

---

## Álbum de recuerdos

La sección **Álbum** (`album.html`) permite armar un libro digital con portada BMAS y hojas dobles estilo *scrapbook*. Desde la galería se puede agregar cualquier foto (original, digitalizada, restaurada o retro) asignándole un título personalizado. Quitar una foto del álbum o vaciarlo solo elimina la referencia, manteniendo intactos los archivos en la galería (`/api/scrapbook`).

---

## Tests

```bash
cd backend
pytest -v                                  # todo
pytest tests/test_scanning.py -v           # de a un módulo por vez
```

---

## Estructura

```text
album-digital/
├── README.md
├── main.py                     # punto de entrada para Vercel
├── requirements.txt            # dependencias de producción
├── vercel.json                 # configuración de despliegue en Vercel
├── frontend/
│   ├── index.html              # estudio: digitalizar, diagnosticar, restaurar, presets y retro
│   ├── galeria.html            # originales y resultados, borrado y alta al álbum
│   ├── buscar.html             # búsqueda por color y por similitud
│   ├── album.html              # álbum de recuerdos (portada y hojas dobles)
│   ├── ui.js                   # toasts y diálogos de confirmación / entrada de texto
│   ├── theme.js / theme.css    # paleta azul-violeta y estilos compartidos
│   └── assets/                 # emblema BMAS y favicon
└── backend/
    ├── requirements.txt
    ├── supabase.sql            # esquema de tablas y bucket privado para Supabase
    ├── app/                    # capa de aplicación (API REST + almacenamiento)
    │   ├── main.py             # FastAPI y manejo de errores
    │   ├── config.py           # rutas y variables de entorno
    │   ├── schemas.py          # modelos Pydantic
    │   ├── routers/            # photos, restore, scan, search, gallery, retro, presets, scrapbook
    │   ├── album.py            # gestión de fotos originales e índice
    │   ├── gallery.py          # carpetas scanned/, restored/ y retro/
    │   ├── presets.py          # persistencia de configuraciones guardadas
    │   ├── scrapbook.py        # persistencia del álbum de recuerdos
    │   ├── catalog.py          # catálogo unificado para búsqueda y álbum
    │   └── steps.py            # construcción y validación de pasos de restauración
    ├── album/                  # EL CORE: procesamiento puro, reutilizable e independiente
    │   ├── imageio.py          # decodificación, orientación EXIF y utilidades de imagen
    │   ├── pipeline.py         # contrato de pasos y traza de ejecución
    │   ├── scanning.py         # detección de esquinas, GrabCut y perspectiva
    │   ├── quality.py          # MSE, PSNR y diagnóstico de nitidez, ruido y brillo
    │   ├── restoration.py      # cinco pasos parametrizables de restauración
    │   ├── descriptors.py      # hash perceptual, histogramas HSV y fracción de color
    │   └── retro.py            # estilo retro: paletas, cuantización y dithering
    └── tests/                  # tests unitarios del core, contrato de la API y almacenamiento
```


