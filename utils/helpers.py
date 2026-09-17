# -*- coding: utf-8 -*-
"""
utils/helpers.py
================
Funciones pequeñas y sin estado que usan varios módulos. Nada de reglas de
negocio aquí: las reglas viven en config/rules.py.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any, Iterable

from config import rules


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def configurar_logging(verboso: bool = False) -> logging.Logger:
    nivel = logging.DEBUG if verboso else logging.INFO
    logging.basicConfig(
        level=nivel,
        format="%(asctime)s  %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
    )
    return logging.getLogger("procesador")


# ---------------------------------------------------------------------------
# Texto
# ---------------------------------------------------------------------------

_NULOS = {str(v).strip().lower() for v in rules.VALORES_NULOS}


def es_nulo(valor: Any) -> bool:
    """True si el valor debe considerarse vacío."""
    if valor is None:
        return True
    try:
        # NaN de pandas/numpy
        if valor != valor:  # noqa: PLR0124
            return True
    except (TypeError, ValueError):
        pass
    return str(valor).strip().lower() in _NULOS


def texto(valor: Any) -> str:
    """Convierte cualquier cosa a str limpio; los nulos quedan en ''."""
    if es_nulo(valor):
        return ""
    return str(valor).strip()


def sin_acentos(valor: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", valor)
        if not unicodedata.combining(c)
    )


def slug(valor: Any, maximo: int = 255) -> str:
    """Convierte un texto en un identificador apto para URL de Shopify."""
    base = sin_acentos(texto(valor)).lower()
    base = base.replace("ñ", "n").replace("&", " y ")
    base = re.sub(r"[^a-z0-9]+", "-", base)
    base = re.sub(r"-{2,}", "-", base).strip("-")
    return base[:maximo].strip("-")


def title_case(valor: str) -> str:
    """
    Title Case respetuoso con el español: preposiciones en minúscula y
    palabras de la lista PALABRAS_INTACTAS sin tocar.
    """
    valor = texto(valor)
    if not valor:
        return ""
    intactas = {p.lower(): p for p in rules.PALABRAS_INTACTAS}
    minusculas = {p.lower() for p in rules.PALABRAS_MINUSCULAS}
    palabras = valor.split()
    salida = []
    for i, palabra in enumerate(palabras):
        bajo = palabra.lower()
        if bajo in intactas:
            salida.append(intactas[bajo])
        elif i > 0 and bajo in minusculas:
            salida.append(bajo)
        elif "-" in palabra:
            salida.append("-".join(p.capitalize() for p in palabra.split("-")))
        else:
            salida.append(palabra.capitalize())
    return " ".join(salida)


def normalizar_clave(valor: Any) -> str:
    """
    Clave canónica para comparar nombres de columna: sin acentos, sin
    símbolos, en minúscula. 'Número de artículo*^' -> 'numerodearticulo'.
    """
    base = sin_acentos(texto(valor)).lower()
    return re.sub(r"[^a-z0-9]", "", base)


# ---------------------------------------------------------------------------
# Números
# ---------------------------------------------------------------------------

def a_decimal(valor: Any) -> float | None:
    """
    Convierte '$ 1,299.00', '1299', '1,299 MXN' -> 1299.0
    Devuelve None si no es un número reconocible. Nunca inventa un valor.
    """
    if es_nulo(valor):
        return None
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return float(valor)

    bruto = str(valor).strip()
    for basura in rules.PRECIO_CARACTERES_BASURA:
        bruto = bruto.replace(basura, "")
    bruto = re.sub(r"[^\d,.\-]", "", bruto)
    if not bruto:
        return None

    # Formato europeo 1.299,00 -> 1299.00
    if "," in bruto and "." in bruto:
        if bruto.rfind(",") > bruto.rfind("."):
            bruto = bruto.replace(".", "").replace(",", ".")
        else:
            bruto = bruto.replace(",", "")
    elif "," in bruto:
        entero, _, decimales = bruto.rpartition(",")
        bruto = f"{entero.replace(',', '')}.{decimales}" if len(decimales) in (1, 2) \
            else bruto.replace(",", "")

    try:
        return float(bruto)
    except ValueError:
        return None


def formatear_precio(valor: float | None) -> str:
    if valor is None:
        return ""
    return f"{valor:.{rules.PRECIO_DECIMALES}f}"


def formatear_numero_talla(valor: float) -> str:
    """22.0 -> '22'   22.5 -> '22.5'"""
    if valor == int(valor):
        return str(int(valor))
    return (f"{valor:.1f}").rstrip("0").rstrip(".")


# ---------------------------------------------------------------------------
# Listas
# ---------------------------------------------------------------------------

def unicos_en_orden(items: Iterable[Any]) -> list:
    vistos, salida = set(), []
    for item in items:
        if item not in vistos:
            vistos.add(item)
            salida.append(item)
    return salida


def dividir_por_separadores(valor: Any, separadores: list[str]) -> list[str]:
    """Parte un texto por cualquiera de los separadores dados."""
    base = texto(valor)
    if not base:
        return []
    patron = "|".join(re.escape(s) for s in separadores)
    partes = re.split(patron, base)
    return [p.strip() for p in partes if p.strip()]
