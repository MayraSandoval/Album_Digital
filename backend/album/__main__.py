"""Línea de comandos.

Misma API que el core, sin navegador — útil para el informe (experimentos
comparativos con --steps, métricas con `metrics`) y para automatizar:

    python -m album restore foto.jpg restaurada.png [--denoise MÉTODO] [--no-scratches] [--no-contrast] [--steps CARPETA]
    python -m album scan mesa.jpg digitalizada.png
    python -m album metrics original.png restaurada.png

"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from album import (
    AlbumError,
    NotImplementedYet,
    RestorationOptions,
    RestorationPipeline,
    decode,
    encode_png,
)
from album.scanning import Scanner

SYMBOLS = {"done": "✓", "pending": "·", "blocked": "-", "failed": "✗"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m album",
        description="Álbum digital: digitalizá, restaurá y organizá fotos.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_restore = sub.add_parser("restore", help="Restaura una foto dañada.")
    p_restore.add_argument("entrada", type=Path)
    p_restore.add_argument("salida", type=Path)
    p_restore.add_argument("--denoise", choices=["auto", "median", "bilateral", "none"], default="auto")
    p_restore.add_argument("--no-scratches", action="store_true", help="desactiva la reparación de rasguños")
    p_restore.add_argument("--no-contrast", action="store_true", help="desactiva el realce de contraste")
    p_restore.add_argument("--steps", type=Path, metavar="CARPETA", help="guarda la imagen de cada paso acá")

    p_scan = sub.add_parser("scan", help="Endereza la foto de una foto impresa.")
    p_scan.add_argument("entrada", type=Path)
    p_scan.add_argument("salida", type=Path)

    p_metrics = sub.add_parser("metrics", help="MSE y PSNR entre dos imágenes del mismo tamaño.")
    p_metrics.add_argument("imagen_a", type=Path)
    p_metrics.add_argument("imagen_b", type=Path)

    args = parser.parse_args(argv)

    if args.command == "restore":
        return _restore(args)
    if args.command == "scan":
        return _scan(args)
    return _metrics(args)


def _read(path: Path):
    try:
        return decode(path.read_bytes())
    except OSError as exc:
        print(f"No se pudo leer {path}: {exc.strerror or exc}", file=sys.stderr)
        sys.exit(1)
    except AlbumError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)


def _restore(args) -> int:
    image = _read(args.entrada)
    options = RestorationOptions(
        denoise=args.denoise,
        repair_scratches=not args.no_scratches,
        contrast=not args.no_contrast,
    )
    trace = RestorationPipeline().run(image, options)
    for result in trace.results:
        line = f"{SYMBOLS[result.status]} {result.step.number}. {result.step.label}"
        if result.message:
            line += f"  ({result.message})"
        print(line)
        if args.steps and result.image is not None:
            args.steps.mkdir(parents=True, exist_ok=True)
            name = f"{result.step.number:02d}-{result.step.name}.png"
            (args.steps / name).write_bytes(encode_png(result.image))
    if trace.failure is not None:
        print(f"FALLÓ: {trace.failure.message}", file=sys.stderr)
        return 1
    args.salida.write_bytes(encode_png(trace.image))
    suffix = "" if trace.complete else " (faltan pasos)"
    print(f"Restaurada guardada en {args.salida}{suffix}")
    return 0


def _scan(args) -> int:
    image = _read(args.entrada)
    try:
        warped = Scanner().scan(image)
    except AlbumError as exc:
        print(exc, file=sys.stderr)
        return 1
    args.salida.write_bytes(encode_png(warped))
    print(f"Digitalizada guardada en {args.salida}")
    return 0


def _metrics(args) -> int:
    from album.quality import mse, psnr

    a = _read(args.imagen_a)
    b = _read(args.imagen_b)
    if a.shape != b.shape:
        print(f"Las imágenes no tienen el mismo tamaño: {a.shape[:2]} contra {b.shape[:2]}.", file=sys.stderr)
        return 1
    try:
        m, p = mse(a, b), psnr(a, b)
    except NotImplementedYet as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"MSE:  {m:.4f}")
    print(f"PSNR: {p:.2f} dB" if p != float("inf") else "PSNR: inf (imágenes idénticas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
