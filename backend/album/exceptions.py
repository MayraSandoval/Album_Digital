"""Excepciones del dominio.

"""


class AlbumError(Exception):
    """Clase base de todos los errores del core."""


class InvalidImage(AlbumError):
    """Los bytes no se pueden abrir como imagen (vacíos, corruptos, no es una imagen)."""


class DocumentNotFound(AlbumError):
    """No se encontró una foto impresa de cuatro esquinas en la imagen."""


class NotImplementedYet(AlbumError):
    """Lanzada por las funciones y pasos que siguen siendo un TODO.

    Mientras exista, la API responde 501 y el pipeline de restauración saltea
    el paso, así la aplicación funciona desde el minuto uno.
    """

    def __init__(self, where: str) -> None:
        super().__init__(f"{where} todavía no está implementado (archivo correspondiente en album/).")
        self.where = where
