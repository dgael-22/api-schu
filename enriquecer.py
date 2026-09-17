# -*- coding: utf-8 -*-
"""
enriquecer.py
=============
Entrada por línea de comandos del enriquecedor. Toda la lógica vive en
enriquecedor/tarea.py, que es la misma que usa la API.

    python enriquecer.py                     usa output/reporte_proceso.xlsx
    python enriquecer.py --limite 5          prueba con 5 artículos
    python enriquecer.py --reconstruir-indice
    python enriquecer.py --ver-navegador     abre el navegador a la vista

Salida: output/enriquecido.xlsx con tres hojas —Encontrados, No encontrados
y Discrepancias—. Nada se publica solo.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

from enriquecedor.fuentes import marcas_soportadas          # noqa: E402
from enriquecedor.tarea import enriquecer_catalogo, enriquecer_imagenes  # noqa: E402

CARPETA_OUTPUT = RAIZ / "output"
log = logging.getLogger("enriquecer")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Completa artículos incompletos con datos del sitio de la marca.")
    parser.add_argument("--faltantes", default=str(CARPETA_OUTPUT / "reporte_proceso.xlsx"),
                        help="reporte del procesador o lista propia (.xlsx/.csv)")
    parser.add_argument("--origen", default=str(RAIZ / "input" / "concentrado fp(2).xlsx"),
                        help="concentrado, para sacar los EAN de cada artículo")
    parser.add_argument("--marca", default="flexi",
                        help="marca por defecto cuando el archivo no la trae")
    parser.add_argument("--salida", default=str(CARPETA_OUTPUT / "enriquecido.xlsx"))
    parser.add_argument("--limite", type=int, default=None,
                        help="tope de artículos a consultar (para probar)")
    parser.add_argument("--reconstruir-indice", action="store_true")
    parser.add_argument("--ver-navegador", action="store_true",
                        help="abre el navegador a la vista, para depurar")
    parser.add_argument("--imagenes", action="store_true",
                        help="en vez de los artículos huérfanos, busca las IMÁGENES "
                             "de los productos que salieron con pocas o ninguna")
    parser.add_argument("--minimo-imagenes", type=int, default=1,
                        help="con --imagenes: cuántas fotos debe tener un producto "
                             "para dejarlo en paz (por defecto 1)")
    parser.add_argument("--export", default=str(CARPETA_OUTPUT / "products_export_limpio.csv"),
                        help="con --imagenes: el CSV ya generado para Shopify")
    parser.add_argument("--verboso", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verboso else logging.INFO,
                        format="%(asctime)s  %(levelname)-8s %(message)s",
                        datefmt="%H:%M:%S")
    log.info("Marcas con fuente registrada: %s", marcas_soportadas())

    if args.imagenes:
        ruta_export = Path(args.export)
        if not ruta_export.exists():
            log.error("No encontré %s. Corre primero: python main.py", ruta_export)
            return 1
        resultado = enriquecer_imagenes(
            ruta_export=ruta_export,
            ruta_salida=Path(args.salida).with_name("imagenes_encontradas.xlsx"),
            minimo=args.minimo_imagenes,
            marca_por_defecto=args.marca,
            limite=args.limite,
            carpeta_indices=CARPETA_OUTPUT,
            reconstruir_indice=args.reconstruir_indice,
            headless=not args.ver_navegador,
        )
        return _informar(resultado)

    ruta_faltantes = Path(args.faltantes)
    if not ruta_faltantes.exists():
        log.error("No encontré %s. Corre primero: python main.py", ruta_faltantes)
        return 1

    resultado = enriquecer_catalogo(
        ruta_reporte=ruta_faltantes,
        ruta_salida=Path(args.salida),
        ruta_origen=Path(args.origen),
        marca_por_defecto=args.marca,
        limite=args.limite,
        carpeta_indices=CARPETA_OUTPUT,
        reconstruir_indice=args.reconstruir_indice,
        headless=not args.ver_navegador,
    )

    return _informar(resultado)


def _informar(resultado) -> int:
    """Imprime el desenlace, igual para los dos modos."""
    if not resultado.ok:
        log.error("%s", resultado.error)
        return 1

    if resultado.solicitados == 0:
        print("\nNada que completar. Todos los productos están bien.\n")
        return 0

    log.info("Encontrados: %d  ·  No encontrados: %d  ·  Discrepancias: %d",
             resultado.encontrados, resultado.no_encontrados, resultado.discrepancias)
    if resultado.marcas_sin_fuente:
        log.warning("Marcas sin fuente registrada: %s",
                    ", ".join(resultado.marcas_sin_fuente))
    if resultado.ruta_salida:
        log.info("Reporte escrito en %s", resultado.ruta_salida)

    print("\nRevisa el archivo antes de subir nada: lo encontrado sale como")
    print("borrador y con la URL de donde salió cada dato.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
