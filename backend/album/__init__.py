"""Core de procesamiento: lo reutilizan la API (app/) y la consola (__main__).

Estructura del core:

- imageio.py ........ Abrir/guardar imágenes y la ficha técnica.
- pipeline.py ....... El corredor de pasos de restauración (estilo TP-3).
- exceptions.py ..... Excepciones de dominio.
- scanning.py ....... Digitalizar una foto impresa.
- quality.py ........ Métricas y diagnóstico de calidad.
- restoration.py .... Los pasos de restauración.
- descriptors.py .... Hash perceptual y descriptores de color.

"""

from album.exceptions import AlbumError, DocumentNotFound, InvalidImage, NotImplementedYet
from album.imageio import ImageInfo, decode, encode_png, inspect, limit_side, to_pil
from album.pipeline import RestorationOptions, RestorationPipeline, Step, StepResult, Trace

__all__ = [
    "AlbumError",
    "DocumentNotFound",
    "ImageInfo",
    "InvalidImage",
    "NotImplementedYet",
    "RestorationOptions",
    "RestorationPipeline",
    "Step",
    "StepResult",
    "Trace",
    "decode",
    "encode_png",
    "inspect",
    "limit_side",
    "to_pil",
]
