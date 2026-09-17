# -*- coding: utf-8 -*-
"""
processors/cleaner.py
=====================
Limpieza conservadora de texto y números. La regla de oro de este módulo es
que ninguna limpieza puede cambiar el significado del dato: se quitan
espacios, saltos de línea y caracteres rotos por codificación, pero jamás se
reescribe un nombre, un color o un precio.
"""

from __future__ import annotations

import logging
import re

import pandas as pd

from config import rules
from utils.helpers import a_decimal, es_nulo, texto, title_case

log = logging.getLogger("procesador.limpieza")

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_ESPACIOS = re.compile(r"[ \t ​]+")


def limpiar_texto(valor) -> str:
    """
    '   NIKE   ' -> 'NIKE'
    'TENIS\n\n  NEGRO' -> 'TENIS NEGRO'
    Corrige el mojibake conocido pero NO cambia mayúsculas ni palabras.
    """
    valor = texto(valor)
    if not valor:
        return ""

    if rules.LIMPIAR_MOJIBAKE:
        for malo, bueno in rules.CORRECCIONES_MOJIBAKE.items():
            if malo in valor:
                valor = valor.replace(malo, bueno)

    valor = _CONTROL.sub("", valor)

    if rules.LIMPIAR_SALTOS_DE_LINEA:
        valor = valor.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")

    if rules.LIMPIAR_ESPACIOS_DOBLES:
        valor = _ESPACIOS.sub(" ", valor)

    return valor.strip()


def limpiar_html(valor) -> str:
    """
    Igual que limpiar_texto pero conservando los saltos de línea como <br>
    cuando el contenido va a una columna HTML.
    """
    valor = texto(valor)
    if not valor:
        return ""
    if rules.LIMPIAR_MOJIBAKE:
        for malo, bueno in rules.CORRECCIONES_MOJIBAKE.items():
            valor = valor.replace(malo, bueno)
    valor = _CONTROL.sub("", valor)
    valor = re.sub(r"(\r\n|\r|\n)+", "<br>", valor)
    valor = _ESPACIOS.sub(" ", valor)
    return valor.strip()


def limpiar_identificador(valor) -> str:
    """
    Para SKU, EAN y códigos: quita espacios y caracteres invisibles pero
    CONSERVA los ceros a la izquierda ('001245' sigue siendo '001245') y
    elimina el apóstrofo que Excel antepone al texto numérico.
    """
    valor = texto(valor)
    if not valor:
        return ""
    valor = valor.lstrip("'").strip()
    valor = _ESPACIOS.sub("", valor)
    valor = _CONTROL.sub("", valor)
    # '1390014023.0' (pandas leyó un número) -> '1390014023'
    if re.fullmatch(r"\d+\.0+", valor):
        valor = valor.split(".")[0]
    return valor


def limpiar_precio(valor) -> tuple[str, str | None]:
    """
    Devuelve (precio_formateado, motivo_de_error).
    El valor económico nunca se modifica: sólo se cambia el formato.
    """
    if es_nulo(valor):
        return "", "precio_vacio"

    numero = a_decimal(valor)
    if numero is None:
        return "", "precio_invalido"
    if numero < rules.PRECIO_MINIMO_VALIDO or numero > rules.PRECIO_MAXIMO_VALIDO:
        return "", "precio_invalido"

    return f"{numero:.{rules.PRECIO_DECIMALES}f}", None


def limpiar_color(valor) -> str:
    color = limpiar_texto(valor)
    if not color:
        return ""
    if rules.NORMALIZAR_COLOR == "titulo":
        return title_case(color)
    if rules.NORMALIZAR_COLOR == "mayusculas":
        return color.upper()
    return color


def limpiar_titulo(valor) -> str:
    titulo = limpiar_texto(valor)
    if not titulo:
        return ""
    if rules.NORMALIZAR_TITULO == "titulo":
        return title_case(titulo)
    if rules.NORMALIZAR_TITULO == "mayusculas":
        return titulo.upper()
    return titulo


def limpiar_dataframe(df: pd.DataFrame, columnas_identificador: list[str] | None = None) -> pd.DataFrame:
    """
    Aplica la limpieza a todas las columnas de texto de un DataFrame.
    Las columnas listadas en columnas_identificador reciben el tratamiento
    especial de códigos (se conservan ceros a la izquierda).
    """
    columnas_identificador = set(columnas_identificador or [])
    limpio = df.copy()
    for columna in limpio.columns:
        if columna in columnas_identificador:
            limpio[columna] = limpio[columna].map(limpiar_identificador)
        else:
            limpio[columna] = limpio[columna].map(limpiar_texto)
    return limpio


def quitar_filas_vacias(df: pd.DataFrame, columnas_clave: list[str]) -> tuple[pd.DataFrame, int]:
    """Descarta filas sin ninguno de los campos clave. Devuelve (df, descartadas)."""
    antes = len(df)
    presentes = [c for c in columnas_clave if c in df.columns]
    if not presentes:
        return df, 0
    mascara = df[presentes].apply(lambda fila: any(texto(v) for v in fila), axis=1)
    return df[mascara].reset_index(drop=True), antes - int(mascara.sum())
