# -*- coding: utf-8 -*-
"""
processors/excel_reader.py
==========================
Lectura de los dos archivos de entrada. Este módulo NO transforma datos:
sólo abre los archivos, encuentra las hojas y columnas que importan y
devuelve DataFrames en crudo (todo como texto, para no perder ceros a la
izquierda ni convertir EANs a notación científica).

Los archivos originales se abren siempre en modo lectura. Nada de lo que
hace este proyecto los modifica.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from config import rules
from utils.helpers import normalizar_clave, texto

log = logging.getLogger("procesador.lector")


class ErrorDeLectura(Exception):
    """El archivo no se puede leer o le faltan columnas indispensables."""


# ---------------------------------------------------------------------------
# Detección de columnas por alias
# ---------------------------------------------------------------------------

def detectar_columnas(columnas: list[str], campos: list[str] | None = None) -> dict[str, str]:
    """
    Empareja los nombres reales de columna con los campos lógicos definidos
    en rules.COLUMN_ALIASES. La comparación ignora mayúsculas, acentos,
    espacios y símbolos, así que 'Número de artículo*^', 'numero de articulo'
    y 'NUMERO_DE_ARTICULO' se reconocen igual.

    Devuelve {campo_logico: nombre_real_de_columna}.
    """
    indice = {}
    for real in columnas:
        indice.setdefault(normalizar_clave(real), real)

    campos = campos or list(rules.COLUMN_ALIASES)
    encontrados: dict[str, str] = {}
    for campo in campos:
        for alias in rules.COLUMN_ALIASES.get(campo, []):
            real = indice.get(normalizar_clave(alias))
            if real is not None:
                encontrados[campo] = real
                break
    return encontrados


# ---------------------------------------------------------------------------
# Tolerancia a archivos desordenados
# ---------------------------------------------------------------------------
# Nada de esto se activa mientras el archivo venga como el concentrado de
# Flexi: primero se intenta lo que dice config/rules.py y sólo si eso falla
# entra la detección automática.

def _puntuar_columnas(columnas: list[str], obligatorias: list[str]) -> int:
    """Cuántos campos obligatorios reconoce este juego de columnas."""
    mapa = detectar_columnas(list(columnas), obligatorias)
    return len(mapa)


def _buscar_fila_encabezado(ruta: Path, hoja: str, obligatorias: list[str]) -> int:
    """
    Devuelve el índice (base 0) de la fila que funciona como encabezado.

    Hay archivos con el logo, el título del reporte o filas en blanco encima de
    los nombres de columna. Se leen las primeras filas sin encabezado y se elige
    la que reconoce más campos obligatorios.
    """
    if not rules.DETECTAR_FILA_ENCABEZADO:
        return 0

    tope = max(1, rules.MAXIMO_FILAS_BUSCAR_ENCABEZADO)
    try:
        muestra = pd.read_excel(ruta, sheet_name=hoja, dtype=str, header=None,
                                nrows=tope, engine="openpyxl")
    except Exception:
        return 0

    mejor, mejor_puntaje = 0, -1
    for i in range(len(muestra)):
        candidatas = [texto(v) for v in muestra.iloc[i].tolist()]
        if not any(candidatas):
            continue
        puntaje = _puntuar_columnas(candidatas, obligatorias)
        if puntaje > mejor_puntaje:
            mejor, mejor_puntaje = i, puntaje

    if mejor:
        log.warning("La hoja '%s' no tiene el encabezado en la primera fila; "
                    "se usa la fila %d.", hoja, mejor + 1)
    return mejor


def _elegir_hoja(ruta: Path, obligatorias: list[str], preferida: str | None = None,
                 excluir: set[str] | None = None) -> tuple[str, int] | None:
    """
    Elige la hoja que mejor cumple con los campos obligatorios.
    Devuelve (nombre_de_hoja, fila_de_encabezado) o None si ninguna sirve.
    """
    hojas = pd.ExcelFile(ruta, engine="openpyxl").sheet_names
    excluir = (excluir or set()) | set(rules.HOJAS_IGNORADAS)

    orden = ([preferida] if preferida in hojas else []) + \
            [h for h in hojas if h != preferida and h not in excluir]

    mejor = None
    for hoja in orden:
        fila = _buscar_fila_encabezado(ruta, hoja, obligatorias)
        try:
            columnas = pd.read_excel(ruta, sheet_name=hoja, dtype=str,
                                     header=fila, nrows=1,
                                     engine="openpyxl").columns
        except Exception:
            continue
        puntaje = _puntuar_columnas([texto(c) for c in columnas], obligatorias)
        if puntaje >= len(obligatorias):
            return hoja, fila
        if puntaje >= rules.MINIMO_COLUMNAS_PARA_CANDIDATA and \
           (mejor is None or puntaje > mejor[2]):
            mejor = (hoja, fila, puntaje)

    if mejor:
        return mejor[0], mejor[1]
    return None


def _parece_url(valor) -> bool:
    v = texto(valor).lower()
    return v.startswith("http://") or v.startswith("https://") or "://" in v


def _columna_es_urls(serie: pd.Series, muestra: int = 50) -> bool:
    """True si la mayoría de los valores no vacíos de la columna son URLs."""
    valores = [v for v in serie.head(muestra).tolist() if texto(v)]
    if not valores:
        return False
    return sum(1 for v in valores if _parece_url(v)) / len(valores) >= 0.5


def _nombrar_columnas_sin_encabezado(df: pd.DataFrame) -> pd.DataFrame:
    """
    Las columnas sin encabezado se identifican por su CONTENIDO en vez de por
    su posición, que es lo que se rompe en cuanto el proveedor agrega o quita
    una columna.
    """
    if not rules.DETECTAR_COLUMNAS_SIN_NOMBRE_POR_CONTENIDO:
        return df.rename(columns=rules.MAESTRO_COLUMNAS_SIN_NOMBRE)

    renombres: dict[str, str] = {}

    # Si alguna columna CON nombre ya trae las URLs, no hay nada que renombrar.
    # Ojo: no basta con que se llame "Imágenes de la galería"; en el concentrado
    # de Flexi esa columna existe pero viene vacía, y las fotos están en la
    # columna sin encabezado. Por eso se mira el contenido, no el nombre.
    ya_hay_imagenes = any(_columna_es_urls(df[c]) for c in df.columns
                          if not str(c).startswith("Unnamed:"))

    for columna in df.columns:
        if not str(columna).startswith("Unnamed:"):
            continue
        if _columna_es_urls(df[columna]) and not ya_hay_imagenes:
            renombres[columna] = "Links Fotografías"
            ya_hay_imagenes = True
        elif columna in rules.MAESTRO_COLUMNAS_SIN_NOMBRE:
            renombres[columna] = rules.MAESTRO_COLUMNAS_SIN_NOMBRE[columna]

    # Lo que la detección no alcanzó, se resuelve con el mapa por posición,
    # pero sólo para columnas que existen y que nadie renombró antes.
    for columna, nombre in rules.MAESTRO_COLUMNAS_SIN_NOMBRE.items():
        if columna in df.columns and columna not in renombres and \
           nombre not in renombres.values():
            renombres[columna] = nombre

    if renombres:
        log.info("Columnas sin encabezado renombradas: %s", renombres)
    return df.rename(columns=renombres)


def _quitar_filas_de_metadatos(df: pd.DataFrame, mapa: dict[str, str]) -> pd.DataFrame:
    """
    Los exports de Hybris traen filas de metadatos debajo del encabezado. En vez
    de saltar un número fijo (que en otro archivo borraría productos reales), se
    descartan las filas de ARRIBA que no traen número de artículo utilizable.
    """
    modo = rules.MAESTRO_FILAS_METADATOS_MODO
    if modo != "auto":
        saltar = rules.MAESTRO_FILAS_METADATOS
        return df.iloc[saltar:] if saltar else df

    columna = mapa.get("articulo")
    if not columna or columna not in df.columns:
        saltar = rules.MAESTRO_FILAS_METADATOS
        return df.iloc[saltar:] if saltar else df

    quitadas = 0
    for _, fila in df.iterrows():
        valor = texto(fila.get(columna))
        # Un artículo real trae dígitos; "ReferenceFormat" o una celda vacía no.
        if valor and any(c.isdigit() for c in valor):
            break
        quitadas += 1

    if quitadas:
        log.info("Se descartaron %d filas de metadatos arriba del primer producto.",
                 quitadas)
    return df.iloc[quitadas:]


# ---------------------------------------------------------------------------
# Lectura del concentrado del proveedor
# ---------------------------------------------------------------------------

def _leer_hoja(ruta: Path, hoja: str, fila_encabezado: int = 0) -> pd.DataFrame:
    df = pd.read_excel(ruta, sheet_name=hoja, dtype=str, header=fila_encabezado,
                       engine="openpyxl")
    df.columns = [texto(c) if texto(c) else f"Unnamed: {i}"
                  for i, c in enumerate(df.columns)]
    return df


def leer_maestro(ruta: Path) -> tuple[pd.DataFrame, dict[str, str]]:
    """
    Hoja maestro: una fila por producto-color.
    Devuelve (dataframe_sin_metadatos, mapa_de_columnas).
    """
    hojas = pd.ExcelFile(ruta, engine="openpyxl").sheet_names
    obligatorias = list(rules.CAMPOS_OBLIGATORIOS_MAESTRO)

    if rules.DETECTAR_HOJAS_AUTOMATICAMENTE:
        elegida = _elegir_hoja(ruta, obligatorias, preferida=rules.HOJA_MAESTRO)
        if elegida is None:
            raise ErrorDeLectura(
                f"Ninguna hoja de {ruta.name} tiene las columnas obligatorias "
                f"{obligatorias}. Hojas disponibles: {hojas}. "
                f"Añade el nombre real en COLUMN_ALIASES de config/rules.py."
            )
        hoja, fila_encabezado = elegida
        if hoja != rules.HOJA_MAESTRO:
            log.warning("No existe la hoja '%s'; se usa '%s', que es la que trae "
                        "las columnas del maestro.", rules.HOJA_MAESTRO, hoja)
    else:
        if rules.HOJA_MAESTRO not in hojas:
            raise ErrorDeLectura(
                f"No encontré la hoja '{rules.HOJA_MAESTRO}' en {ruta.name}. "
                f"Hojas disponibles: {hojas}"
            )
        hoja, fila_encabezado = rules.HOJA_MAESTRO, 0

    df = _leer_hoja(ruta, hoja, fila_encabezado)

    # Las columnas sin encabezado se resuelven por contenido y, si no, por posición.
    df = _nombrar_columnas_sin_encabezado(df)

    mapa = detectar_columnas(list(df.columns))

    # Metadatos del export por encima del primer producto.
    df = _quitar_filas_de_metadatos(df, mapa).reset_index(drop=True)

    # Fuera filas completamente vacías.
    df = df.dropna(how="all").reset_index(drop=True)

    faltan = [c for c in obligatorias if c not in mapa]
    if faltan:
        raise ErrorDeLectura(
            f"A la hoja '{hoja}' le faltan columnas obligatorias: "
            f"{faltan}. Añade el nombre real en COLUMN_ALIASES de config/rules.py."
        )

    log.info("Maestro '%s' (encabezado en la fila %d): %d productos, %d columnas",
             hoja, fila_encabezado + 1, len(df), len(df.columns))
    return df, mapa


def leer_variantes(ruta: Path) -> tuple[pd.DataFrame, dict[str, str]]:
    """
    Hojas de tallas/EAN/precio. Se concatenan todas y se añade la columna
    _hoja_origen para poder rastrear de dónde salió cada fila.
    """
    disponibles = pd.ExcelFile(ruta, engine="openpyxl").sheet_names
    obligatorias = list(rules.CAMPOS_OBLIGATORIOS_VARIANTES)
    piezas, mapa_final = [], {}

    # Las hojas configuradas primero; si la detección está activa, se revisan
    # además todas las demás por si el proveedor las renombró.
    candidatas = [h for h in rules.HOJAS_VARIANTES if h in disponibles]
    if rules.DETECTAR_HOJAS_AUTOMATICAMENTE:
        candidatas += [h for h in disponibles
                       if h not in candidatas
                       and h not in rules.HOJAS_IGNORADAS]

    for hoja in candidatas:
        fila_encabezado = _buscar_fila_encabezado(ruta, hoja, obligatorias)
        try:
            df = _leer_hoja(ruta, hoja, fila_encabezado)
        except Exception as e:
            log.warning("No pude leer la hoja '%s': %s", hoja, e)
            continue
        df = df.dropna(how="all")
        mapa = detectar_columnas(list(df.columns))
        faltan = [c for c in obligatorias if c not in mapa]
        if faltan:
            if hoja in rules.HOJAS_VARIANTES:
                log.warning("La hoja '%s' no tiene %s; se omite.", hoja, faltan)
            continue

        if hoja not in rules.HOJAS_VARIANTES:
            log.warning("Se detectó la hoja de variantes '%s', que no estaba en "
                        "HOJAS_VARIANTES.", hoja)

        df["_hoja_origen"] = hoja
        piezas.append(df)
        mapa_final = mapa or mapa_final
        log.info("Variantes '%s' (encabezado en la fila %d): %d filas",
                 hoja, fila_encabezado + 1, len(df))

    if not piezas:
        raise ErrorDeLectura(
            "No pude leer ninguna hoja de variantes: ninguna trae "
            f"{obligatorias}. Revisa HOJAS_VARIANTES y COLUMN_ALIASES "
            "en config/rules.py."
        )

    todo = pd.concat(piezas, ignore_index=True, sort=False)
    return todo, mapa_final


# ---------------------------------------------------------------------------
# Lectura de la plantilla de Shopify
# ---------------------------------------------------------------------------

def leer_plantilla(carpeta_input: Path) -> tuple[list[str], pd.DataFrame]:
    """
    La plantilla se usa SÓLO para conocer el nombre y el orden exacto de las
    columnas de salida. Sus productos nunca se copian.
    Acepta .xlsx o .csv.
    """
    for nombre in rules.ARCHIVO_PLANTILLA:
        ruta = carpeta_input / nombre
        if not ruta.exists():
            continue
        if ruta.suffix.lower() in (".xlsx", ".xlsm"):
            df = pd.read_excel(ruta, dtype=str, engine="openpyxl")
        else:
            df = pd.read_csv(ruta, dtype=str, keep_default_na=False,
                             encoding="utf-8-sig", low_memory=False)
        columnas = [texto(c) for c in df.columns]
        log.info("Plantilla '%s': %d columnas, %d filas de ejemplo (no se usan como datos)",
                 ruta.name, len(columnas), len(df))
        return columnas, df

    raise ErrorDeLectura(
        f"No encontré la plantilla. Coloca alguno de estos archivos en input/: "
        f"{rules.ARCHIVO_PLANTILLA}"
    )
