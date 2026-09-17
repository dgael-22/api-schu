# -*- coding: utf-8 -*-
"""
enriquecedor/tarea.py
=====================
El enriquecimiento completo en UNA función reutilizable.

Mismo patrón que processors/pipeline.py: la línea de comandos (enriquecer.py)
y la API (api/rutas_enriquecer.py) llaman aquí, así que las dos hacen
exactamente lo mismo y sólo existe una versión de la lógica.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from .fuentes import crear, marcas_soportadas
from .modelo import Solicitud
from .motor import Motor

log = logging.getLogger("enriquecedor.tarea")


@dataclass
class ResultadoEnriquecimiento:
    ok: bool = True
    error: str = ""
    ruta_salida: Path | None = None
    solicitados: int = 0
    encontrados: int = 0
    no_encontrados: int = 0
    discrepancias: int = 0
    marcas_sin_fuente: list[str] = field(default_factory=list)

    def resumen(self) -> dict:
        return {
            "solicitados": self.solicitados,
            "encontrados": self.encontrados,
            "no_encontrados": self.no_encontrados,
            "discrepancias": self.discrepancias,
            "marcas_sin_fuente": self.marcas_sin_fuente,
        }


# ---------------------------------------------------------------- entrada ---

def leer_solicitudes(ruta: Path, marca_por_defecto: str = "flexi") -> list[Solicitud]:
    """Acepta el reporte del procesador o una lista propia (.xlsx o .csv)."""
    ruta = Path(ruta)
    if ruta.suffix.lower() in (".xlsx", ".xlsm"):
        hojas = pd.ExcelFile(ruta, engine="openpyxl").sheet_names
        hoja = "Problemas" if "Problemas" in hojas else hojas[0]
        df = pd.read_excel(ruta, sheet_name=hoja, dtype=str, engine="openpyxl")
    else:
        df = pd.read_csv(ruta, dtype=str, keep_default_na=False)

    df = df.fillna("")
    columnas = {c.strip().lower(): c for c in df.columns}

    # Del reporte del procesador sólo interesan los huérfanos.
    if "código" in columnas:
        df = df[df[columnas["código"]].str.strip() == "variantes_huerfanas"]

    def col(*nombres):
        for n in nombres:
            if n in columnas:
                return columnas[n]
        return None

    c_art = col("nº artículo", "articulo", "artículo", "prod.sap", "sku")
    if c_art is None:
        raise ValueError(f"No encontré la columna de artículo en {ruta.name}. "
                         f"Columnas: {list(df.columns)}")
    c_marca = col("marca", "vendor")
    c_ean = col("ean", "cod ean/upc", "barcode")
    c_estilo, c_color = col("estilo"), col("color")
    c_titulo = col("título", "titulo", "title")

    solicitudes: list[Solicitud] = []
    for _, fila in df.iterrows():
        articulo = str(fila[c_art]).strip()
        if not articulo:
            continue
        eans = []
        if c_ean and str(fila[c_ean]).strip():
            eans = [e.strip() for e in str(fila[c_ean]).split(",") if e.strip()]
        solicitudes.append(Solicitud(
            articulo=articulo,
            marca=(str(fila[c_marca]).strip() if c_marca else "") or marca_por_defecto,
            eans=eans,
            estilo=str(fila[c_estilo]).strip() if c_estilo else "",
            color=str(fila[c_color]).strip() if c_color else "",
            titulo=str(fila[c_titulo]).strip() if c_titulo else "",
        ))
    return solicitudes


def completar_eans(solicitudes: list[Solicitud], ruta_origen: Path | None) -> None:
    """
    El reporte de problemas no trae los EAN, y el EAN es la mejor llave para
    buscar en el sitio de la marca. Se sacan del concentrado original.
    """
    if not ruta_origen or not Path(ruta_origen).exists():
        log.warning("Sin concentrado a la mano: se busca sólo por número de artículo.")
        return
    try:
        from processors import excel_reader
        df, mapa = excel_reader.leer_variantes(Path(ruta_origen))
    except Exception as e:                                      # noqa: BLE001
        log.warning("No pude leer los EAN del concentrado: %s", e)
        return

    col_art, col_ean = mapa.get("var_articulo"), mapa.get("var_ean")
    if not col_art or not col_ean:
        return

    por_articulo: dict[str, list[str]] = {}
    for _, fila in df.iterrows():
        a, e = str(fila.get(col_art, "")).strip(), str(fila.get(col_ean, "")).strip()
        if a and e:
            por_articulo.setdefault(a, []).append(e)

    for s in solicitudes:
        if not s.eans:
            s.eans = por_articulo.get(s.articulo, [])[:6]


# ----------------------------------------------------------------- salida ---

def escribir_reporte(resultados, discrepancias, ruta: Path) -> tuple[int, int]:
    encontrados, faltantes = [], []
    for r in resultados:
        if r.encontrado:
            f = r.ficha
            encontrados.append({
                "Artículo": r.solicitud.articulo, "Marca": r.solicitud.marca,
                "Título": f.titulo, "Estilo": f.estilo, "Color": f.color,
                "Precio": f.precio, "Moneda": f.moneda,
                "Imágenes": len(f.imagenes), "URLs de imagen": " | ".join(f.imagenes),
                "Campos aportados": ", ".join(r.campos_llenados),
                "Fuente": f.fuente, "URL": f.url_fuente, "Consultado": f.consultado_en,
            })
        else:
            faltantes.append({
                "Artículo": r.solicitud.articulo, "Marca": r.solicitud.marca,
                "EAN consultados": ", ".join(r.solicitud.eans[:3]),
                "Motivo": r.motivo,
            })

    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(ruta, engine="openpyxl") as w:
        pd.DataFrame(encontrados or [{"Artículo": "(ninguno)"}]).to_excel(
            w, sheet_name="Encontrados", index=False)
        pd.DataFrame(faltantes or [{"Artículo": "(ninguno)"}]).to_excel(
            w, sheet_name="No encontrados", index=False)
        pd.DataFrame(discrepancias or [{"articulo": "(ninguna)"}]).to_excel(
            w, sheet_name="Discrepancias", index=False)
    return len(encontrados), len(faltantes)


# ------------------------------------------------------------------ tarea ---

def enriquecer_catalogo(*, ruta_reporte: Path, ruta_salida: Path,
                        ruta_origen: Path | None = None,
                        marca_por_defecto: str = "flexi",
                        limite: int | None = None,
                        carpeta_indices: Path | None = None,
                        reconstruir_indice: bool = False,
                        headless: bool = True) -> ResultadoEnriquecimiento:
    """
    Lee los artículos incompletos, los busca en el sitio de su marca y escribe
    el Excel de resultados. No modifica el catálogo: sólo reporta.
    """
    try:
        solicitudes = leer_solicitudes(Path(ruta_reporte), marca_por_defecto)
    except Exception as e:                                      # noqa: BLE001
        return ResultadoEnriquecimiento(ok=False, error=str(e))

    resultado = ResultadoEnriquecimiento(solicitados=len(solicitudes))
    if not solicitudes:
        log.info("No hay artículos incompletos. Nada que enriquecer.")
        return resultado

    completar_eans(solicitudes, ruta_origen)

    carpeta_indices = Path(carpeta_indices or Path(ruta_salida).parent)
    fuentes, sin_fuente = {}, []
    for marca in {s.marca.lower() for s in solicitudes}:
        fuente = crear(marca,
                       ruta_indice=carpeta_indices / f"indice_{marca}.json",
                       reconstruir_indice=reconstruir_indice,
                       headless=headless)
        if fuente is None:
            sin_fuente.append(marca)
        else:
            fuentes[marca] = fuente
    resultado.marcas_sin_fuente = sorted(sin_fuente)

    if not fuentes:
        return ResultadoEnriquecimiento(
            ok=False,
            error=(f"Ninguna de las marcas {sorted(sin_fuente)} tiene fuente. "
                   f"Soportadas: {marcas_soportadas()}. "
                   f"Agrégala en enriquecedor/fuentes/__init__.py"),
            solicitados=len(solicitudes), marcas_sin_fuente=sorted(sin_fuente))

    motor = Motor(fuentes, limite=limite)
    try:
        resultados = motor.enriquecer(solicitudes)
    except RuntimeError as e:      # falta Playwright o el navegador no arrancó
        return ResultadoEnriquecimiento(ok=False, error=str(e),
                                        solicitados=len(solicitudes))

    encontrados, faltantes = escribir_reporte(resultados, motor.discrepancias,
                                              Path(ruta_salida))
    resultado.ruta_salida = Path(ruta_salida)
    resultado.encontrados = encontrados
    resultado.no_encontrados = faltantes
    resultado.discrepancias = len(motor.discrepancias)
    return resultado


# ------------------------------------------------- imágenes desde la marca ---

def leer_solicitudes_sin_imagenes(ruta_export: Path, minimo: int = 1,
                                  marca_por_defecto: str = "flexi") -> list[Solicitud]:
    """
    Lee el CSV/Excel ya generado para Shopify y devuelve los productos que
    tienen MENOS de `minimo` imágenes.

    Las llaves de búsqueda salen del propio export: `Variant SKU` es el número
    SAP y `Variant Barcode` el EAN, que son justo los dos identificadores con
    los que el sitio de la marca indexa sus fichas.
    """
    ruta = Path(ruta_export)
    if ruta.suffix.lower() in (".xlsx", ".xlsm"):
        df = pd.read_excel(ruta, dtype=str, engine="openpyxl").fillna("")
    else:
        df = pd.read_csv(ruta, dtype=str, keep_default_na=False, low_memory=False)

    faltantes = {"Handle", "Title", "Image Src"} - set(df.columns)
    if faltantes:
        raise ValueError(f"A {ruta.name} le faltan columnas: {sorted(faltantes)}")

    solicitudes: list[Solicitud] = []
    for handle, grupo in df.groupby("Handle", sort=False):
        cuantas = (grupo["Image Src"].astype(str).str.strip() != "").sum()
        if cuantas >= minimo:
            continue

        cabecera = grupo[grupo["Title"].astype(str).str.strip() != ""]
        cabecera = cabecera.iloc[0] if len(cabecera) else grupo.iloc[0]

        skus = [s for s in grupo.get("Variant SKU", pd.Series(dtype=str)).astype(str)
                if s.strip()]
        eans = [b for b in grupo.get("Variant Barcode", pd.Series(dtype=str)).astype(str)
                if b.strip()]

        solicitudes.append(Solicitud(
            articulo=(skus[0] if skus else str(handle)),
            marca=str(cabecera.get("Vendor", "")).strip() or marca_por_defecto,
            eans=list(dict.fromkeys(eans))[:6],
            titulo=str(cabecera.get("Title", "")).strip(),
        ))
    return solicitudes


def escribir_imagenes_para_shopify(resultados, ruta_csv: Path) -> int:
    """
    Escribe un CSV mínimo que Shopify importa tal cual para agregar imágenes:
    Handle, Image Src, Image Position. No toca nada más del producto.
    """
    filas = []
    for r in resultados:
        if not r.encontrado:
            continue
        for posicion, url in enumerate(r.ficha.imagenes, start=1):
            filas.append({"Handle": r.solicitud.articulo,
                          "Image Src": url,
                          "Image Position": posicion})
    ruta_csv = Path(ruta_csv)
    ruta_csv.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(filas or [{"Handle": "", "Image Src": "", "Image Position": ""}]).to_csv(
        ruta_csv, index=False, encoding="utf-8-sig")
    return len(filas)


def enriquecer_imagenes(*, ruta_export: Path, ruta_salida: Path,
                        minimo: int = 1, marca_por_defecto: str = "flexi",
                        limite: int | None = None,
                        carpeta_indices: Path | None = None,
                        reconstruir_indice: bool = False,
                        headless: bool = True) -> ResultadoEnriquecimiento:
    """
    Busca en el sitio de la marca las imágenes de los productos que salieron
    con menos de `minimo` fotos, y escribe:

        <salida>            reporte con lo encontrado y lo que no
        <salida sin ext>_shopify.csv   Handle / Image Src / Image Position

    Igual que siempre: no pisa nada del catálogo, sólo reporta y deja el CSV
    para que una persona lo revise antes de importarlo.
    """
    try:
        solicitudes = leer_solicitudes_sin_imagenes(Path(ruta_export), minimo,
                                                    marca_por_defecto)
    except Exception as e:                                      # noqa: BLE001
        return ResultadoEnriquecimiento(ok=False, error=str(e))

    resultado = ResultadoEnriquecimiento(solicitados=len(solicitudes))
    if not solicitudes:
        log.info("Todos los productos tienen al menos %d imagen(es). Nada que hacer.",
                 minimo)
        return resultado

    log.info("Productos con menos de %d imagen(es): %d", minimo, len(solicitudes))

    carpeta_indices = Path(carpeta_indices or Path(ruta_salida).parent)
    fuentes, sin_fuente = {}, []
    for marca in {s.marca.lower() for s in solicitudes}:
        fuente = crear(marca,
                       ruta_indice=carpeta_indices / f"indice_{marca}.json",
                       reconstruir_indice=reconstruir_indice, headless=headless)
        if fuente is None:
            sin_fuente.append(marca)
        else:
            fuentes[marca] = fuente
    resultado.marcas_sin_fuente = sorted(sin_fuente)

    if not fuentes:
        return ResultadoEnriquecimiento(
            ok=False,
            error=(f"Ninguna de las marcas {sorted(sin_fuente)} tiene fuente. "
                   f"Soportadas: {marcas_soportadas()}."),
            solicitados=len(solicitudes), marcas_sin_fuente=sorted(sin_fuente))

    motor = Motor(fuentes, limite=limite)
    try:
        resultados = motor.enriquecer(solicitudes)
    except RuntimeError as e:
        return ResultadoEnriquecimiento(ok=False, error=str(e),
                                        solicitados=len(solicitudes))

    encontrados, faltantes = escribir_reporte(resultados, motor.discrepancias,
                                              Path(ruta_salida))
    ruta_csv = Path(ruta_salida).with_name(Path(ruta_salida).stem + "_shopify.csv")
    cuantas = escribir_imagenes_para_shopify(resultados, ruta_csv)
    log.info("CSV de imágenes para Shopify: %s (%d filas)", ruta_csv, cuantas)

    resultado.ruta_salida = Path(ruta_salida)
    resultado.encontrados = encontrados
    resultado.no_encontrados = faltantes
    resultado.discrepancias = len(motor.discrepancias)
    return resultado
