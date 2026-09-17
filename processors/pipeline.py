# -*- coding: utf-8 -*-
"""
processors/pipeline.py
======================
El proceso completo, en una sola función reutilizable.

Existe para que main.py (línea de comandos) y la API (api/app.py) hagan
exactamente lo mismo sin duplicar código. Si mañana se añade una interfaz
Streamlit o un cron, también llamará aquí.

    resultado = procesar_catalogo(
        ruta_origen=Path("input/concentrado fp(2).xlsx"),
        carpeta_salida=Path("output"),
    )
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from config import rules
from processors import excel_reader, exporter, images, products, validator

log = logging.getLogger("procesador.pipeline")


@dataclass
class Resultado:
    """Todo lo que produjo una ejecución."""
    ok: bool = True
    error: str = ""

    ruta_excel: Path | None = None
    ruta_csv: Path | None = None
    ruta_reporte: Path | None = None

    productos_leidos: int = 0
    productos_exportados: int = 0
    productos_con_advertencia: int = 0
    productos_rechazados: int = 0
    variantes_leidas: int = 0
    variantes_exportadas: int = 0
    imagenes_exportadas: int = 0
    filas_generadas: int = 0
    columnas: int = 0

    originales_intactos: bool = True
    segundos: float = 0.0
    inventario: str = ""
    inventario_rastreado: bool = False
    conteo_problemas: dict[str, int] = field(default_factory=dict)
    mapa_maestro: dict[str, str] = field(default_factory=dict)
    mapa_variantes: dict[str, str] = field(default_factory=dict)

    def resumen(self) -> dict:
        """Versión serializable, para devolver como JSON desde la API."""
        return {
            "ok": self.ok,
            "error": self.error,
            "productos_leidos": self.productos_leidos,
            "productos_exportados": self.productos_exportados,
            "productos_con_advertencia": self.productos_con_advertencia,
            "productos_rechazados": self.productos_rechazados,
            "variantes_leidas": self.variantes_leidas,
            "variantes_exportadas": self.variantes_exportadas,
            "imagenes_exportadas": self.imagenes_exportadas,
            "filas_generadas": self.filas_generadas,
            "columnas": self.columnas,
            "originales_intactos": self.originales_intactos,
            "segundos": round(self.segundos, 2),
            "inventario": self.inventario,
            "inventario_rastreado": self.inventario_rastreado,
            "problemas": self.conteo_problemas,
            "columnas_detectadas": {
                "maestro": self.mapa_maestro,
                "variantes": self.mapa_variantes,
            },
        }


def _huella(ruta: Path) -> str:
    return hashlib.md5(ruta.read_bytes()).hexdigest()


def procesar_catalogo(*, ruta_origen: Path, carpeta_salida: Path,
                      ruta_plantilla: Path | None = None,
                      validar_imagenes: bool = False,
                      generar_csv: bool | None = None,
                      nombre_excel: str | None = None,
                      nombre_csv: str | None = None,
                      nombre_reporte: str | None = None,
                      inventario: str | None = None,
                      inventario_rastreado: bool | None = None) -> Resultado:
    """
    Ejecuta el proceso entero y devuelve un Resultado.

    ruta_origen      Excel del proveedor. NO se modifica.
    carpeta_salida   dónde escribir los archivos generados.
    ruta_plantilla   plantilla de columnas (.xlsx o .csv). Si es None se busca
                     en la carpeta del origen.
    validar_imagenes comprobar por red que las URLs devuelvan una imagen.
    inventario       cantidad para "Variant Inventory Qty" (por defecto, la de
                     config/rules.py).
    inventario_rastreado
                     si Shopify debe descontar al vender. Con False la columna
                     "Variant Inventory Tracker" va vacía y la cantidad no
                     cambia nunca.

    Nunca lanza excepción por un dato malo: los problemas van al reporte. Sólo
    devuelve ok=False si el archivo no se puede leer.
    """
    inicio = time.time()
    resultado = Resultado()
    carpeta_salida.mkdir(parents=True, exist_ok=True)

    generar_csv = rules.GENERAR_CSV_SHOPIFY if generar_csv is None else generar_csv
    inventario = str(rules.INVENTARIO_POR_DEFECTO if inventario is None else inventario)
    inventario_rastreado = (rules.INVENTARIO_RASTREADO if inventario_rastreado is None
                            else bool(inventario_rastreado))
    nombre_excel = nombre_excel or rules.ARCHIVO_SALIDA
    nombre_csv = nombre_csv or rules.ARCHIVO_SALIDA_CSV
    nombre_reporte = nombre_reporte or rules.ARCHIVO_REPORTE

    huella_antes = _huella(ruta_origen)

    # ---------------- 1. lectura ----------------
    try:
        if ruta_plantilla is not None and ruta_plantilla.exists():
            if ruta_plantilla.suffix.lower() in (".xlsx", ".xlsm"):
                df_plantilla = pd.read_excel(ruta_plantilla, dtype=str, engine="openpyxl")
            else:
                df_plantilla = pd.read_csv(ruta_plantilla, dtype=str, keep_default_na=False,
                                           encoding="utf-8-sig", low_memory=False)
            columnas_plantilla = [str(c).strip() for c in df_plantilla.columns]
        else:
            columnas_plantilla, _ = excel_reader.leer_plantilla(ruta_origen.parent)

        df_maestro, mapa_maestro = excel_reader.leer_maestro(ruta_origen)
        df_variantes, mapa_variantes = excel_reader.leer_variantes(ruta_origen)
    except excel_reader.ErrorDeLectura as exc:
        resultado.ok = False
        resultado.error = str(exc)
        resultado.segundos = time.time() - inicio
        return resultado
    except Exception as exc:                                    # noqa: BLE001
        resultado.ok = False
        resultado.error = f"No pude leer el archivo: {type(exc).__name__}: {exc}"
        resultado.segundos = time.time() - inicio
        return resultado

    resultado.mapa_maestro = dict(mapa_maestro)
    resultado.mapa_variantes = dict(mapa_variantes)
    resultado.productos_leidos = len(df_maestro)
    resultado.variantes_leidas = len(df_variantes)
    resultado.columnas = len(columnas_plantilla)

    # ---------------- 2. limpieza, normalización, transformación ----------------
    variantes_por_articulo, incidencias_var = products.construir_variantes(
        df_variantes, mapa_variantes)
    lista_productos, incidencias_prod = products.construir_productos(
        df_maestro, mapa_maestro, variantes_por_articulo)

    # ---------------- 3. imágenes ----------------
    verificacion = {}
    if validar_imagenes or rules.VALIDAR_URLS_IMAGENES:
        anterior = rules.VALIDAR_URLS_IMAGENES
        rules.VALIDAR_URLS_IMAGENES = True
        try:
            verificacion = images.verificar_urls(
                [u for p in lista_productos for u in p.imagenes])
        finally:
            rules.VALIDAR_URLS_IMAGENES = anterior

    # ---------------- 4. validación ----------------
    exportables, rechazados, hallazgos = validator.validar(
        lista_productos, incidencias_var + incidencias_prod, verificacion)

    # ---------------- 5. exportación ----------------
    # Las columnas de la plantilla, en su orden, y al final las de los filtros
    # de la tienda (metafields), para que entren en la misma importación.
    columnas_salida = exporter.columnas_con_filtros(columnas_plantilla)
    resultado.columnas = len(columnas_salida)
    df_salida = exporter.construir_filas(
        exportables, columnas_salida,
        inventario=inventario, inventario_rastreado=inventario_rastreado)
    resultado.ruta_excel = carpeta_salida / nombre_excel
    exporter.exportar_productos(df_salida, resultado.ruta_excel)

    if generar_csv:
        resultado.ruta_csv = carpeta_salida / nombre_csv
        exporter.exportar_csv(df_salida, resultado.ruta_csv)

    hojas = exporter.construir_reporte(
        productos_totales=resultado.productos_leidos, exportables=exportables,
        rechazados=rechazados, hallazgos=hallazgos, filas_generadas=len(df_salida),
        variantes_leidas=resultado.variantes_leidas, mapa_maestro=mapa_maestro,
        mapa_variantes=mapa_variantes, columnas_plantilla=columnas_plantilla,
        verificacion_imagenes=verificacion,
        inventario=inventario, inventario_rastreado=inventario_rastreado)
    resultado.ruta_reporte = carpeta_salida / nombre_reporte
    exporter.exportar_reporte(hojas, resultado.ruta_reporte)

    # ---------------- 6. cifras y comprobación de integridad ----------------
    resultado.productos_exportados = len(exportables)
    resultado.productos_rechazados = len(rechazados)
    resultado.productos_con_advertencia = len(
        {h.handle for h in hallazgos if h.nivel == "advertencia" and h.handle})
    resultado.variantes_exportadas = sum(len(p.variantes) for p in exportables)
    resultado.imagenes_exportadas = sum(len(p.imagenes) for p in exportables)
    resultado.filas_generadas = len(df_salida)
    resultado.inventario = inventario
    resultado.inventario_rastreado = inventario_rastreado

    conteo: dict[str, int] = {}
    for hallazgo in hallazgos:
        conteo[hallazgo.codigo] = conteo.get(hallazgo.codigo, 0) + 1
    resultado.conteo_problemas = dict(sorted(conteo.items(), key=lambda kv: -kv[1]))

    resultado.originales_intactos = _huella(ruta_origen) == huella_antes
    if not resultado.originales_intactos:
        log.error("El archivo de origen cambió durante el proceso.")

    resultado.segundos = time.time() - inicio
    return resultado
