# -*- coding: utf-8 -*-
"""
main.py
=======
Punto de entrada de línea de comandos.

    python main.py                      proceso normal
    python main.py --validar-imagenes   además comprueba por red las URLs
    python main.py --verboso            más detalle en pantalla
    python main.py --origen otro.xlsx   usa otro archivo de input/

Toda la lógica vive en processors/pipeline.py, que es la misma que usa la API.
Los archivos de input/ se abren en modo lectura y nunca se modifican.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

from config import rules                               # noqa: E402
from processors.pipeline import procesar_catalogo      # noqa: E402
from utils.helpers import configurar_logging           # noqa: E402

CARPETA_INPUT = RAIZ / "input"
CARPETA_OUTPUT = RAIZ / "output"


def parsear_argumentos():
    parser = argparse.ArgumentParser(
        description="Convierte el Excel del proveedor en un Excel listo para Shopify.")
    parser.add_argument("--validar-imagenes", action="store_true",
                        help="comprueba por red que cada URL devuelva una imagen")
    parser.add_argument("--verboso", action="store_true", help="salida detallada")
    parser.add_argument("--origen", default=None,
                        help="otro archivo de origen dentro de input/")
    return parser.parse_args()


def main() -> int:
    args = parsear_argumentos()
    log = configurar_logging(args.verboso)

    ruta_origen = CARPETA_INPUT / (args.origen or rules.ARCHIVO_ORIGEN)
    if not ruta_origen.exists():
        log.error("No encontré '%s' en input/.", ruta_origen.name)
        log.error("Archivos disponibles: %s",
                  [p.name for p in CARPETA_INPUT.glob('*') if p.is_file()] or "(vacía)")
        return 1

    print()
    log.info("=" * 68)
    log.info("PROCESADOR Y NORMALIZADOR DE CATÁLOGOS PARA SHOPIFY")
    log.info("=" * 68)

    # Huellas de TODA la carpeta input, para demostrar que nada se tocó.
    def huellas() -> dict[str, str]:
        return {p.name: hashlib.md5(p.read_bytes()).hexdigest()
                for p in CARPETA_INPUT.glob("*")
                if p.is_file() and not p.name.startswith(".")}

    antes = huellas()

    resultado = procesar_catalogo(
        ruta_origen=ruta_origen,
        carpeta_salida=CARPETA_OUTPUT,
        validar_imagenes=args.validar_imagenes,
    )

    if not resultado.ok:
        log.error("%s", resultado.error)
        return 1

    if antes != huellas():
        log.error("¡ALERTA! Un archivo de input/ cambió durante el proceso.")
        return 2
    log.info("Archivos originales intactos (verificado por MD5).")

    print()
    log.info("-" * 68)
    log.info("  Productos leídos ........ %d", resultado.productos_leidos)
    log.info("  Productos exportados .... %d", resultado.productos_exportados)
    log.info("  Con advertencias ........ %d", resultado.productos_con_advertencia)
    log.info("  Rechazados por error .... %d", resultado.productos_rechazados)
    log.info("  Variantes exportadas .... %d", resultado.variantes_exportadas)
    log.info("  Filas del Excel ......... %d", resultado.filas_generadas)
    log.info("-" * 68)
    for ruta in (resultado.ruta_excel, resultado.ruta_csv, resultado.ruta_reporte):
        if ruta:
            log.info("  output/%s", ruta.name)
    log.info("  Terminado en %.1f s", resultado.segundos)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
